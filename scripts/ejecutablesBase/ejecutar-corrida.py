#!/usr/bin/env python3
"""Corrida completa del agente, con verificación y almacén en un solo comando.

Entrypoint que el ADR-0006, `docs/operations/despliegue.md` y
`docs/development/entorno.md` ya daban por existente. Es el archivo único que
encadena el flujo completo, y el mismo que invoca `corrida-programada.yml`: un
solo código, dos disparadores.

1. Corre la suite de tests y la **categoriza** (`--con-tests`).
2. Lee **todos** los logs de Supabase (`--desde-supabase`) o, por defecto, el
   dataset del canal monitoreo, comparándolo contra su bloque `esperado`.
3. Ejecuta el flujo multiagente —triage, especialistas, consolidación— y deja
   la corrida persistida en Supabase.
4. Emite los hallazgos como SARIF para GitHub code scanning (`--sarif`).
5. Levanta el panel en `127.0.0.1:8080` para revisar y aprobar (`--panel`).

Nunca presenta un fallo como éxito: si el almacén no está configurado lo declara
y sigue; si falla, lo dice; si el presupuesto corta la corrida, la marca parcial
y nombra lo que quedó pendiente. Es la misma regla del `mock`/`live` de
`AGENTS.md`.

Uso:
    python3 scripts/ejecutablesBase/ejecutar-corrida.py --mode mock --con-tests
    python3 scripts/ejecutablesBase/ejecutar-corrida.py --caso monitoreo-camino-feliz-01
    python3 scripts/ejecutablesBase/ejecutar-corrida.py --verificar-almacen

    # el flujo entero en local, en un comando
    python3 scripts/ejecutablesBase/ejecutar-corrida.py --con-tests --desde-supabase         --sarif evals/results/incidentes.sarif --json-out evals/results/corrida.json --panel
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.maas_demo.almacen import Almacen, AlmacenError  # noqa: E402
from src.maas_demo.config import Config, ConfigError  # noqa: E402
from src.maas_demo.dotenv import load_dotenv  # noqa: E402
from src.maas_demo.orchestrator import MemoryStore, Orchestrator  # noqa: E402
from src.maas_demo.provider import ProviderError, build_provider  # noqa: E402
from src.maas_demo.sarif import construir_sarif  # noqa: E402
from src.maas_demo.server import create_server  # noqa: E402
from src.maas_demo.service import ChatService  # noqa: E402


DATASET_MONITOREO = PROJECT_ROOT / "projects" / "monitoreo" / "data" / "monitoreo_dumps.jsonl"
INVENTARIO = Path("evals") / "results" / "incidentes-supabase.jsonl"
SECCIONES = ("Tipo de incidente", "Causa raíz", "Evidencia", "Qué se descartó", "Acción correctiva")

# Cada módulo de test cae en una categoría legible para el resumen final.
CATEGORIAS = {
    "test_monitoreo_generator": "generador-monitoreo",
    "test_contrato_canonico": "contrato-canonico",
    "test_almacen": "conexion-supabase",
    "test_full_flow": "flujo-agente",
    "test_corrida": "corrida-unica",
    "test_sarif": "salida-sarif",
}
CATEGORIA_POR_DEFECTO = "vertical-slice"


# ===========================================================================
# Tests categorizados
# ===========================================================================

def categoria_de(test: unittest.TestCase) -> str:
    modulo = type(test).__module__.rsplit(".", 1)[-1]
    return CATEGORIAS.get(modulo, CATEGORIA_POR_DEFECTO)


class ResultadoCategorizado(unittest.TextTestResult):
    """Agrupa el resultado por categoría en vez de dar un único total."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.por_categoria: dict[str, dict] = {}

    def _registrar(self, test, estado: str, motivo: str = "") -> None:
        fila = self.por_categoria.setdefault(
            categoria_de(test), {"total": 0, "ok": 0, "falla": 0, "skip": 0, "motivos": []}
        )
        fila["total"] += 1
        fila[estado] += 1
        if motivo and motivo not in fila["motivos"]:
            fila["motivos"].append(motivo)

    def addSuccess(self, test):
        super().addSuccess(test)
        self._registrar(test, "ok")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._registrar(test, "falla")

    def addError(self, test, err):
        super().addError(test, err)
        self._registrar(test, "falla")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._registrar(test, "skip", reason)


def correr_tests(verbosidad: int = 0) -> tuple[bool, dict]:
    suite = unittest.defaultTestLoader.discover(str(PROJECT_ROOT / "tests"), top_level_dir=str(PROJECT_ROOT))
    runner = unittest.TextTestRunner(
        stream=open(os.devnull, "w") if verbosidad == 0 else sys.stderr,
        verbosity=verbosidad,
        resultclass=ResultadoCategorizado,
    )
    resultado = runner.run(suite)
    return resultado.wasSuccessful(), resultado.por_categoria


def imprimir_categorias(por_categoria: dict) -> None:
    print()
    print(f"  {'CATEGORIA':<22}{'TOTAL':>6}{'OK':>5}{'FALLA':>7}{'SKIP':>6}")
    print("  " + "-" * 46)
    totales = {"total": 0, "ok": 0, "falla": 0, "skip": 0}
    for categoria in sorted(por_categoria):
        fila = por_categoria[categoria]
        for clave in totales:
            totales[clave] += fila[clave]
        print(
            f"  {categoria:<22}{fila['total']:>6}{fila['ok']:>5}"
            f"{fila['falla']:>7}{fila['skip']:>6}"
        )
    print("  " + "-" * 46)
    print(
        f"  {'TOTAL':<22}{totales['total']:>6}{totales['ok']:>5}"
        f"{totales['falla']:>7}{totales['skip']:>6}"
    )
    # los omitidos se declaran con su motivo: nunca se ocultan
    for categoria in sorted(por_categoria):
        for motivo in por_categoria[categoria]["motivos"]:
            print(f"    omitido en {categoria}: {motivo}")
    escribir_resumen_actions(por_categoria, totales)


def escribir_resumen_actions(por_categoria: dict, totales: dict) -> None:
    """Publica la tabla en el resumen del job cuando corre en GitHub Actions."""
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if not destino:
        return

    icono = "❌" if totales["falla"] else "✅"
    lineas = [
        f"## {icono} Pruebas por categoría",
        "",
        "| Categoría | Total | OK | Falla | Omitido |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for categoria in sorted(por_categoria):
        f = por_categoria[categoria]
        lineas.append(
            f"| `{categoria}` | {f['total']} | {f['ok']} | {f['falla']} | {f['skip']} |"
        )
    lineas.append(
        f"| **TOTAL** | **{totales['total']}** | **{totales['ok']}** "
        f"| **{totales['falla']}** | **{totales['skip']}** |"
    )

    motivos = [
        f"- `{categoria}`: {motivo}"
        for categoria in sorted(por_categoria)
        for motivo in por_categoria[categoria]["motivos"]
    ]
    if motivos:
        lineas += ["", "**Omitidos, con su motivo:**", ""] + motivos

    with open(destino, "a", encoding="utf-8") as resumen:
        resumen.write("\n".join(lineas) + "\n\n")


# ===========================================================================
# Flujo del agente
# ===========================================================================

def cargar_volcados(ruta: Path) -> list[dict]:
    if not ruta.is_file():
        raise SystemExit(f"[error] no existe el dataset: {ruta}")
    texto = ruta.read_text(encoding="utf-8")
    if ruta.suffix == ".jsonl":
        casos = [json.loads(linea) for linea in texto.splitlines() if linea.strip()]
    else:
        casos = json.loads(texto)
    if not isinstance(casos, list) or not casos:
        raise SystemExit(f"[error] el dataset esta vacio o no es una lista: {ruta}")
    return casos


def contrastar(contenido: str, esperado: dict) -> dict:
    """Compara la respuesta contra el groundtruth del volcado.

    Es deliberadamente textual: sin el orquestador en main no hay JSON
    estructurado que comparar, pero saber si el reporte nombra el tipo correcto
    ya es señal util.
    """
    texto = contenido.lower()
    ruteo = esperado.get("ruteo", {})
    tipos = {datos["tipo"] for datos in ruteo.values()}
    return {
        "tipos_esperados": sorted(tipos),
        "tipos_nombrados": sorted(t for t in tipos if t.replace("-", " ") in texto or t in texto),
        "secciones_presentes": [s for s in SECCIONES if s.lower() in texto],
        "incidentes_esperados": esperado.get("incidentes", esperado.get("incidentes_detectados")),
    }


def ejecutar_caso(servicio: ChatService, caso: dict) -> dict:
    try:
        resultado = servicio.complete([{"role": "user", "content": caso["prompt"]}])
    except ProviderError as error:
        return {"id": caso["id"], "ok": False, "error": str(error)}

    contenido = resultado["content"]
    contraste = contrastar(contenido, caso.get("esperado", {}))
    completo = len(contraste["secciones_presentes"]) >= 3
    return {
        "id": caso["id"],
        "segmento": caso.get("segment"),
        "ok": bool(contenido.strip()) and completo,
        "modo": resultado.get("mode"),
        "modelo": resultado.get("model"),
        "latencia_ms": resultado.get("latency_ms"),
        "contraste": contraste,
    }


# ===========================================================================
# Flujo multiagente alimentado por Supabase
# ===========================================================================

def _texto_incidente(fila: dict) -> str:
    logs = fila.get("logs_adjuntos") or []
    if isinstance(logs, str):
        logs = [logs]
    # Sin nada que analizar no se fabrica un volcado: las etiquetas por si
    # solas darian un prompt no vacio y el agente razonaria sobre el aire.
    if not (fila.get("titulo") or fila.get("descripcion") or logs):
        return ""
    partes = [
        f"TICKET {fila.get('ticket_numero', 's/n')}: {fila.get('titulo', '')}",
        f"Sistema afectado: {fila.get('sistema_afectado', 'no declarado')}",
        f"Severidad declarada: {fila.get('severidad', 'no declarada')}",
        fila.get("descripcion", ""),
    ]
    partes += [f"LOG: {json.dumps(linea, ensure_ascii=False) if not isinstance(linea, str) else linea}"
               for linea in logs]
    return "\n".join(parte for parte in partes if parte)


def _texto_email(fila: dict) -> str:
    if not (fila.get("asunto") or fila.get("cuerpo")):
        return ""
    return "\n".join([
        f"De: {fila.get('remitente', 'desconocido')}",
        f"Asunto: {fila.get('asunto', '')}",
        fila.get("cuerpo", ""),
    ])


def volcados_desde_supabase(config: Config) -> list[dict]:
    """Todo lo que hay en Supabase, convertido en volcados para el orquestador.

    Se leen las dos tablas de entrada completas —`consultar_todo` pagina, porque
    PostgREST corta en 1000 filas—. El contenido son datos a analizar: el
    orquestador ya trata los logs como datos y nunca como instrucciones.
    """
    if not config.hay_almacen:
        raise SystemExit("[almacen] faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY: no hay logs que repasar.")
    almacen = Almacen(url=config.supabase_url, service_key=config.supabase_key)

    volcados: list[dict] = []
    for tabla, canal, formatear in (
        ("incidentes", "monitoreo", _texto_incidente),
        ("emails_entrantes", "email-soporte", _texto_email),
    ):
        try:
            filas = almacen.consultar_todo(tabla)
        except AlmacenError as error:
            print(f"[almacen] no se pudo leer '{tabla}': {error}")
            continue
        print(f"[almacen] {tabla}: {len(filas)} fila(s)")
        for fila in filas:
            prompt = formatear(fila).strip()
            if prompt:
                volcados.append({
                    "id": fila.get("ticket_numero") or fila.get("message_id") or fila.get("id", ""),
                    "origen": f"{tabla}/{fila.get('id', '')}",
                    "canal": canal,
                    "prompt": prompt,
                })
    return volcados


def escribir_inventario(volcados: list[dict], ruta: Path) -> None:
    """Deja en disco lo que se leyó: es a lo que apuntan las alertas del SARIF."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as archivo:
        for volcado in volcados:
            archivo.write(json.dumps(volcado, ensure_ascii=False) + "\n")


def orquestar(config: Config, volcados: list[dict], presupuesto_minutos: float) -> tuple[list[dict], list[dict]]:
    """Corre el flujo multiagente sobre cada volcado. Devuelve (corridas, pendientes).

    El presupuesto corta entre volcados, nunca a mitad de uno. Lo que quedó sin
    procesar se devuelve para declararlo: una corrida truncada no se presenta
    como completa.
    """
    store = MemoryStore()
    orquestador = Orchestrator(config, store)
    limite = time.monotonic() + presupuesto_minutos * 60 if presupuesto_minutos > 0 else None

    corridas: list[dict] = []
    for indice, volcado in enumerate(volcados, start=1):
        if limite is not None and time.monotonic() >= limite:
            print(f"[flujo] presupuesto de {presupuesto_minutos:g} min agotado.")
            return corridas, volcados[indice - 1:]

        etiqueta = f"{volcado['id']}"[:34]
        run_id, persistida = "", True
        try:
            for evento in orquestador.stream(volcado):
                run_id = run_id or evento.get("run_id", "")
            resultado = store.get(run_id)
        except (ProviderError, ValueError, TypeError) as error:
            # El orquestador guarda en memoria antes de persistir. Si lo que
            # falló fue la escritura en Supabase, el análisis es válido y se
            # conserva: se declara el fallo, no se descarta el trabajo hecho.
            resultado = store.get(run_id) if run_id else None
            if resultado is None:
                print(f"  {etiqueta:<34} FALLO: {error}")
                continue
            persistida = False
            print(f"  {etiqueta:<34} SIN PERSISTIR: {error}")

        if resultado is None:
            print(f"  {etiqueta:<34} FALLO: la corrida no dejó resultado.")
            continue

        resultado |= {"origen": volcado["origen"], "linea": indice, "persistida": persistida}
        corridas.append(resultado)
        print(
            f"  {etiqueta:<34} {resultado['status']:<11}"
            f" incidentes={len(resultado['triage']['incidentes'])}"
            f" hallazgos={len(resultado['hallazgos'])}"
            f" fallidos={resultado['fallidos']}"
            f" {resultado['latency_ms']}ms"
        )
    return corridas, []


def escribir_sarif(corridas: list[dict], ruta: Path) -> int:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    documento = construir_sarif(corridas, inventario=INVENTARIO.as_posix())
    ruta.write_text(json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8")
    total = len(documento["runs"][0]["results"])
    print(f"[sarif] {total} alerta(s) en {ruta}")
    return total


def flujo_supabase(config: Config, args: argparse.Namespace) -> int:
    volcados = volcados_desde_supabase(config)
    if not volcados:
        print("[almacen] no hay logs que repasar. No se inventa una corrida.")
        return 1

    escribir_inventario(volcados, PROJECT_ROOT / INVENTARIO)
    print(f"\n[flujo] modo={config.mode} modelo={config.model} volcados={len(volcados)}")
    corridas, pendientes = orquestar(config, volcados, args.presupuesto_minutos)

    hallazgos = sum(len(c["hallazgos"]) for c in corridas)
    sin_persistir = [c["origen"] for c in corridas if not c["persistida"]]
    print(f"\n[flujo] {len(corridas)}/{len(volcados)} volcados procesados, {hallazgos} hallazgos.")
    if pendientes:
        print(f"[flujo] PARCIAL: {len(pendientes)} volcados quedaron sin procesar.")
    if sin_persistir:
        print(f"[flujo] {len(sin_persistir)} corridas se analizaron pero NO quedaron en Supabase.")

    if args.sarif:
        escribir_sarif(corridas, args.sarif)

    resumen = {
        "modo": config.mode,
        "modelo": config.model,
        "fuente": "supabase",
        "volcados": len(volcados),
        "procesados": len(corridas),
        "pendientes": [v["origen"] for v in pendientes],
        "sin_persistir": sin_persistir,
        "hallazgos": hallazgos,
        "estado": "parcial" if pendientes or sin_persistir else "completada",
        "corridas": [
            {k: c[k] for k in ("run_id", "origen", "status", "llamadas", "latency_ms",
                               "fallidos", "persistida")}
            for c in corridas
        ],
    }
    escribir_resumen_supabase(resumen)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[salida] {args.json_out}")

    return 0 if corridas and not pendientes and not sin_persistir else 1


def escribir_resumen_supabase(resumen: dict) -> None:
    """Publica el resultado de la corrida en el resumen del job de Actions."""
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if not destino:
        return
    icono = "⚠️" if resumen["estado"] == "parcial" else "✅"
    lineas = [
        f"## {icono} Corrida sobre Supabase ({resumen['modo']})",
        "",
        f"- Volcados leídos: **{resumen['volcados']}**",
        f"- Procesados: **{resumen['procesados']}**",
        f"- Hallazgos: **{resumen['hallazgos']}**",
        f"- Estado: **{resumen['estado']}**",
    ]
    if resumen["pendientes"]:
        lineas += ["", f"Sin procesar por presupuesto: {len(resumen['pendientes'])}."]
    if resumen["sin_persistir"]:
        lineas += ["", f"Analizadas pero no guardadas en Supabase: {len(resumen['sin_persistir'])}."]
    with open(destino, "a", encoding="utf-8") as resumen_actions:
        resumen_actions.write("\n".join(lineas) + "\n\n")


def levantar_panel(config: Config) -> None:
    servidor = create_server(config, host="127.0.0.1", port=8080)
    print("\n[panel] http://127.0.0.1:8080 — Ctrl+C para salir.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n[panel] detenido.")
    finally:
        servidor.server_close()


# ===========================================================================
# Almacén
# ===========================================================================

def verificar_almacen(config: Config) -> int:
    if not config.hay_almacen:
        print("[almacen] SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY no estan definidas.")
        print("          Sin ellas no se puede verificar la conexion. No se asume exito.")
        return 2
    try:
        almacen = Almacen(url=config.supabase_url, service_key=config.supabase_key)
        conteos = almacen.verificar()
    except AlmacenError as error:
        print(f"[almacen] FALLO: {error}")
        return 1

    print("[almacen] conexion establecida. Filas por tabla:")
    hubo_error = False
    for tabla, valor in conteos.items():
        print(f"    {tabla:<22} {valor}")
        hubo_error = hubo_error or str(valor).startswith("error:")
    return 1 if hubo_error else 0


def leer_tabla(config: Config, tabla: str, limite: int = 20) -> int:
    """Vuelca una tabla del almacén, para inspeccionar qué hay guardado."""
    if not config.hay_almacen:
        print("[almacen] faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY.")
        return 2
    try:
        almacen = Almacen(url=config.supabase_url, service_key=config.supabase_key)
        filas = almacen.consultar(tabla, limite=limite)
    except AlmacenError as error:
        print(f"[almacen] {error}")
        return 1

    print(f"[almacen] tabla '{tabla}': {len(filas)} fila(s)")
    if not filas:
        return 0
    print(f"[almacen] columnas: {', '.join(filas[0])}")
    for fila in filas:
        print("-" * 70)
        for clave, valor in fila.items():
            texto = str(valor).replace("\n", " ")
            print(f"  {clave:<22} {texto[:110]}{'...' if len(texto) > 110 else ''}")
    return 0


def guardar_corrida(config: Config, resumen: dict) -> None:
    if not config.hay_almacen:
        print("[almacen] sin credenciales: la corrida no se persiste.")
        return
    try:
        almacen = Almacen(url=config.supabase_url, service_key=config.supabase_key)
        almacen.insertar("incidente_eventos", {"detalle": json.dumps(resumen, ensure_ascii=False)})
        print("[almacen] corrida registrada.")
    except AlmacenError as error:
        print(f"[almacen] no se pudo registrar la corrida: {error}")


# ===========================================================================
# CLI
# ===========================================================================

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Ejecuta el flujo del agente y su verificacion.")
    ap.add_argument("--mode", choices=("mock", "live"), help="fuerza el modo del proveedor")
    ap.add_argument("--dataset", type=Path, default=DATASET_MONITOREO,
                    help="volcados de entrada (default: dataset del canal monitoreo)")
    ap.add_argument("--caso", default="", help="ejecuta solo el volcado con ese id")
    ap.add_argument("--limite", type=int, default=3, help="maximo de volcados a ejecutar (default 3)")
    ap.add_argument("--con-tests", action="store_true", help="corre la suite antes del flujo")
    ap.add_argument("--solo-tests", action="store_true", help="corre la suite y sale")
    ap.add_argument("--verificar-almacen", action="store_true",
                    help="comprueba la conexion a Supabase y sale")
    ap.add_argument("--leer-tabla", default="",
                    help="muestra las filas de una tabla del almacen y sale")
    ap.add_argument("--json-out", type=Path, help="escribe el resumen de la corrida")
    ap.add_argument("--desde-supabase", action="store_true",
                    help="repasa todos los logs del almacen con el flujo multiagente")
    ap.add_argument("--sarif", type=Path,
                    help="escribe los hallazgos como SARIF para GitHub code scanning")
    ap.add_argument("--presupuesto-minutos", type=float, default=0.0,
                    help="corta la corrida al agotarse y declara lo que quedo pendiente (0 = sin corte)")
    ap.add_argument("--panel", action="store_true",
                    help="levanta el panel en 127.0.0.1:8080 al terminar")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    if args.mode:
        os.environ["MAAS_MODE"] = args.mode

    print("=" * 62)
    print("  Corrida del agente de respuesta a incidentes")
    print("=" * 62)

    # 1. Tests primero: no se gasta saldo en una corrida que ya sabemos rota.
    if args.con_tests or args.solo_tests:
        print("\n[tests] ejecutando la suite...")
        exito, por_categoria = correr_tests()
        imprimir_categorias(por_categoria)
        if not exito:
            print("\n[tests] FALLARON. No se ejecuta el flujo.")
            return 1
        print("\n[tests] suite en verde.")
        if args.solo_tests:
            return 0

    try:
        config = Config.from_env()
    except ConfigError as error:
        print(f"[config] {error}")
        return 2

    if args.verificar_almacen:
        return verificar_almacen(config)

    if args.leer_tabla:
        return leer_tabla(config, args.leer_tabla, limite=max(1, args.limite))

    # 2. El flujo multiagente sobre todo lo que hay en Supabase.
    if args.desde_supabase:
        codigo = flujo_supabase(config, args)
        print("=" * 62)
        if args.panel:
            levantar_panel(config)
        return codigo

    # 2b. El flujo de un solo agente, alimentado por el dataset del canal monitoreo.
    casos = cargar_volcados(args.dataset)
    if args.caso:
        casos = [c for c in casos if c.get("id") == args.caso]
        if not casos:
            raise SystemExit(f"[error] no hay ningun volcado con id={args.caso}")
    casos = casos[: max(1, args.limite)]

    servicio = ChatService(build_provider(config))
    print(f"\n[flujo] modo={config.mode} modelo={config.model} volcados={len(casos)}")
    print(f"[flujo] dataset={args.dataset.relative_to(PROJECT_ROOT)}")

    resultados = []
    for caso in casos:
        print(f"\n[agente] procesando {caso['id']}...")
        r = ejecutar_caso(servicio, caso)
        resultados.append(r)
        if r.get("error"):
            print(f"  {r['id']:<34} FALLO: {r['error']}")
            continue
        c = r["contraste"]
        for seccion in SECCIONES:
            marca = "✓" if seccion in c["secciones_presentes"] else "·"
            print(f"    {marca} {seccion}")
        print(
            f"  {r['id']:<34} {'ok' if r['ok'] else 'incompleto':<11}"
            f" secciones={len(c['secciones_presentes'])}/5"
            f" tipos={len(c['tipos_nombrados'])}/{len(c['tipos_esperados'])}"
            f" {r['latencia_ms']}ms"
        )

    aciertos = sum(1 for r in resultados if r.get("ok"))
    resumen = {
        "modo": config.mode,
        "modelo": config.model,
        "dataset": str(args.dataset.relative_to(PROJECT_ROOT)),
        "volcados": len(resultados),
        "correctos": aciertos,
        "resultados": resultados,
    }
    print(f"\n[flujo] {aciertos}/{len(resultados)} volcados con reporte completo.")

    # 3. Persistencia, declarando siempre lo que pasa.
    guardar_corrida(config, resumen)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[salida] {args.json_out}")

    print("=" * 62)
    if args.panel:
        levantar_panel(config)
    return 0 if aciertos == len(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
