#!/usr/bin/env python3
"""Corrida completa del agente, con verificación y almacén en un solo comando.

Entrypoint que el ADR-0006, `docs/operations/despliegue.md` y
`docs/development/entorno.md` ya daban por existente. Hace tres cosas que hasta
ahora vivían separadas:

1. Corre la suite de tests y la **categoriza** (`--con-tests`).
2. Ejecuta el flujo del agente sobre un volcado, tomándolo por defecto del
   dataset del canal monitoreo (`projects/monitoreo/data/monitoreo_dumps.jsonl`),
   y compara la salida contra el bloque `esperado` — algo que `evaluar.py` no
   hace, porque solo lee `id`, `segment` y `prompt`.
3. Persiste el resultado en Supabase si hay credenciales.

Nunca presenta un fallo como éxito: si el almacén no está configurado lo declara
y sigue; si falla, lo dice. Es la misma regla del `mock`/`live` de `AGENTS.md`.

Uso:
    python3 scripts/ejecutablesBase/ejecutar-corrida.py --mode mock --con-tests
    python3 scripts/ejecutablesBase/ejecutar-corrida.py --caso monitoreo-camino-feliz-01
    python3 scripts/ejecutablesBase/ejecutar-corrida.py --verificar-almacen
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.maas_demo.almacen import Almacen, AlmacenError  # noqa: E402
from src.maas_demo.config import Config, ConfigError  # noqa: E402
from src.maas_demo.dotenv import load_dotenv  # noqa: E402
from src.maas_demo.provider import ProviderError, build_provider  # noqa: E402
from src.maas_demo.service import ChatService  # noqa: E402


DATASET_MONITOREO = PROJECT_ROOT / "projects" / "monitoreo" / "data" / "monitoreo_dumps.jsonl"
SECCIONES = ("Tipo de incidente", "Causa raíz", "Evidencia", "Qué se descartó", "Acción correctiva")

# Cada módulo de test cae en una categoría legible para el resumen final.
CATEGORIAS = {
    "test_monitoreo_generator": "generador-monitoreo",
    "test_contrato_canonico": "contrato-canonico",
    "test_almacen": "conexion-supabase",
    "test_full_flow": "flujo-agente",
    "test_corrida": "corrida-unica",
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

    # 2. El flujo, alimentado por el dataset del canal monitoreo.
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
    return 0 if aciertos == len(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
