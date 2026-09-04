#!/usr/bin/env python3
"""
Trazabilidad de punta a punta: de lo que pasa de verdad a lo que el agente hace.

El problema que resuelve: hoy se puede decir "el agente detectó 2 incidentes",
pero no *cuáles* ni *de qué señal salieron*. El contraste comparaba conjuntos de
tipos, así que acertar el tipo de otro incidente contaba como acierto y detectar
el incidente correcto con otro nombre contaba como fallo.

La clave que hace posible la atribución exacta ya estaba en el bus y no se usaba:

    cada incidente real es DUEÑO de sus `lineas[].texto`,
    y esos textos son los que viajan literalmente al feed de monitoreo
    y a los logs del semáforo.

Entonces, si el agente cita una línea como evidencia, se sabe con certeza qué
incidente real estaba mirando. No hace falta emparejar por tipo, ni por servicio,
ni por ventana temporal: la evidencia citada *es* la clave de correlación.

Sobre eso se construyen dos cosas:

  1. LINAJE — por cada incidente real: qué canales lo publicaron, cuántas líneas
     puso cada uno, si llegó al volcado, si el agente lo detectó, qué
     especialista lo diagnosticó y qué acción propuso.

  2. EMBUDO — cuántos incidentes sobreviven cada salto, y la conversión de cada
     uno. Es la respuesta a "lo que se tiene vs lo que procesa el agente".

Este módulo vive en el puente a propósito: es el único componente que puede ver
la verdad y la salida del agente a la vez. El agente sigue ciego (AGENTS.md).
"""

from __future__ import annotations

import re
from typing import Any

# Los canales reformatean la línea antes de publicarla:
#   monitoreo -> "MONITOREO 00:26:04 evento=deploy release=v360 ..."
#   logs      -> "00:26:04 ERROR evento=deploy release=v360 ..."
# El prefijo se recorta para comparar contra el texto que el bus considera suyo.
_PREFIJO_CANAL = re.compile(
    r"^\s*(?:MONITOREO|DEV-CHAT|EMAIL|LOGS)?\s*"       # etiqueta de canal opcional
    r"(?:\d{2}:\d{2}:\d{2})?\s*"                        # hora opcional
    r"(?:ERROR|WARNING|INFO|CRITICAL)?\s*",             # nivel opcional
    re.IGNORECASE,
)

# Debajo de esto, una coincidencia parcial es ruido: "value=0" aparece en medio
# repo. El umbral va en caracteres y no en porcentaje porque las líneas de log
# tienen longitudes muy distintas.
MIN_CARACTERES_ANCLAJE = 24


def normalizar(texto: str) -> str:
    """Espacios colapsados y minúsculas. Sin esto, un canal que reindenta rompe
    la comparación aunque el contenido sea idéntico."""
    return " ".join(str(texto).split()).lower()


def sin_prefijo(texto: str) -> str:
    """Quita la etiqueta de canal, la hora y el nivel de log."""
    return _PREFIJO_CANAL.sub("", str(texto), count=1).strip()


class IndiceDeLineas:
    """Mapa línea -> incidente real que la emitió.

    Guarda la forma normalizada y sin prefijo de cada línea del groundtruth. Al
    consultar, admite contención en los dos sentidos: el agente a veces cita la
    línea completa con su prefijo de canal, y a veces solo el fragmento que le
    importó.
    """

    def __init__(self, verdad: dict[str, Any]):
        self._entradas: list[tuple[str, str]] = []
        for incidente in verdad.get("incidentes", []):
            for linea in incidente.get("lineas", []):
                clave = normalizar(sin_prefijo(linea.get("texto", "")))
                if len(clave) >= MIN_CARACTERES_ANCLAJE:
                    self._entradas.append((clave, incidente["incidente_id"]))

    def __len__(self) -> int:
        return len(self._entradas)

    def atribuir(self, cita: str) -> str | None:
        """Devuelve el incidente_id real dueño de esta cita, o None si no ancla.

        Se prefiere la coincidencia más larga: si dos incidentes comparten un
        fragmento corto, gana el que comparte más texto.
        """
        candidata = normalizar(sin_prefijo(cita))
        if len(candidata) < MIN_CARACTERES_ANCLAJE:
            return None
        mejor: tuple[int, str] | None = None
        for clave, incidente_id in self._entradas:
            if clave in candidata or candidata in clave:
                largo = min(len(clave), len(candidata))
                if mejor is None or largo > mejor[0]:
                    mejor = (largo, incidente_id)
        return mejor[1] if mejor else None


def atribuir_deteccion(deteccion: dict[str, Any], indice: IndiceDeLineas) -> dict[str, Any]:
    """Ancla un incidente detectado por el agente contra la verdad, por evidencia.

    Un incidente cuyas citas no anclan en ningún lado es un falso positivo: el
    agente reportó algo que no salió de ninguna señal real.
    """
    votos: dict[str, int] = {}
    ancladas: list[str] = []
    no_ancladas: list[str] = []
    for cita in deteccion.get("evidencia", []):
        incidente_id = indice.atribuir(cita)
        if incidente_id:
            votos[incidente_id] = votos.get(incidente_id, 0) + 1
            ancladas.append(cita)
        else:
            no_ancladas.append(cita)
    ganador = max(votos, key=lambda k: votos[k]) if votos else None
    return {
        "detectado_id": deteccion.get("id"),
        "incidente_real": ganador,
        "votos": votos,
        "citas_ancladas": ancladas,
        "citas_no_ancladas": no_ancladas,
        "falso_positivo": ganador is None,
    }


def _accion_de(hallazgos: list[dict[str, Any]], detectado_id: str) -> dict[str, Any] | None:
    for hallazgo in hallazgos:
        if hallazgo.get("incidente_id") == detectado_id and hallazgo.get("accion"):
            return hallazgo["accion"]
    return None


def _identificadores(valor: Any) -> set[str]:
    """Los identificadores que aparecen en un valor, para comparar la acción
    propuesta contra la esperada sin exigir que los nombres de campo coincidan."""
    if isinstance(valor, dict):
        return {str(v).strip() for v in valor.values() if str(v).strip()}
    return {str(valor).strip()} if str(valor).strip() else set()


def construir_linaje(
    verdad: dict[str, Any],
    triage: dict[str, Any] | None,
    hallazgos: list[dict[str, Any]],
    canales: dict[str, Any],
) -> list[dict[str, Any]]:
    """Una fila por incidente REAL activo, con todo su recorrido.

    Es la trazabilidad "de problemas en cada pantalla": para cada problema, por
    dónde salió y hasta dónde llegó.
    """
    indice = IndiceDeLineas(verdad)
    detecciones = (triage or {}).get("incidentes", [])
    atribuciones = [atribuir_deteccion(d, indice) for d in detecciones]
    por_real: dict[str, list[dict[str, Any]]] = {}
    for atribucion, deteccion in zip(atribuciones, detecciones):
        if atribucion["incidente_real"]:
            por_real.setdefault(atribucion["incidente_real"], []).append(
                {"deteccion": deteccion, "atribucion": atribucion}
            )

    # Qué llegó de verdad al volcado que se le entregó al agente.
    volcado_texto = normalizar(
        " ".join(
            linea
            for lineas in canales.values()
            if lineas
            for linea in lineas
        )
    )

    linaje: list[dict[str, Any]] = []
    for incidente in verdad.get("incidentes", []):
        if incidente.get("resuelto"):
            continue
        real_id = incidente["incidente_id"]
        lineas = incidente.get("lineas", [])
        en_volcado = sum(
            1
            for linea in lineas
            if len(normalizar(linea.get("texto", ""))) >= MIN_CARACTERES_ANCLAJE
            and normalizar(linea["texto"]) in volcado_texto
        )
        emparejados = por_real.get(real_id, [])
        deteccion = emparejados[0]["deteccion"] if emparejados else None
        detectado_id = deteccion.get("id") if deteccion else None

        hallazgos_del = [
            h for h in hallazgos
            if h.get("incidente_id") == detectado_id and h.get("estado") == "completado"
        ]
        accion = _accion_de(hallazgos, detectado_id) if detectado_id else None
        esperada = incidente.get("accion_esperada") or {}

        accion_correcta = None
        if esperada.get("action_id"):
            if accion is None:
                accion_correcta = False
            else:
                mismo_id = accion.get("action_id") == esperada["action_id"]
                ids_esperados = _identificadores(esperada.get("params_clave", {}))
                ids_propuestos = _identificadores(accion.get("params", {}))
                accion_correcta = bool(mismo_id and (not ids_esperados or ids_esperados & ids_propuestos))

        ruteo_esperado = incidente.get("ruteo_defecto")
        especialistas_usados = sorted({h["especialista"] for h in hallazgos_del})

        linaje.append({
            "incidente_real": real_id,
            "escenario": incidente.get("escenario"),
            "tipo_real": incidente.get("tipo"),
            "severidad_real": incidente.get("severidad"),
            "servicio": incidente.get("servicio"),
            "panel_semaforo": incidente.get("panel_semaforo"),
            # --- por dónde salió (trazabilidad por pantalla)
            "canales_que_lo_publicaron": sorted(incidente.get("reportado_en", {}).keys()),
            "lineas_emitidas": len(lineas),
            "lineas_en_volcado": en_volcado,
            # --- qué hizo el agente con él
            "detectado": deteccion is not None,
            "detectado_como": detectado_id,
            "titulo_agente": deteccion.get("titulo") if deteccion else None,
            "tipo_agente": deteccion.get("tipo") if deteccion else None,
            "severidad_agente": deteccion.get("severidad") if deteccion else None,
            "tipo_correcto": (deteccion.get("tipo") == incidente.get("tipo")) if deteccion else None,
            "severidad_correcta": (deteccion.get("severidad") == incidente.get("severidad")) if deteccion else None,
            "citas_ancladas": len(emparejados[0]["atribucion"]["citas_ancladas"]) if emparejados else 0,
            "citas_no_ancladas": len(emparejados[0]["atribucion"]["citas_no_ancladas"]) if emparejados else 0,
            # --- quién lo diagnosticó
            "ruteo_esperado": ruteo_esperado,
            "especialistas_asignados": deteccion.get("especialistas", []) if deteccion else [],
            "especialistas_que_respondieron": especialistas_usados,
            "ruteo_correcto": (ruteo_esperado in (deteccion.get("especialistas") or [])) if deteccion and ruteo_esperado else None,
            "diagnosticado": bool(hallazgos_del),
            "causa_raiz": hallazgos_del[0].get("causa_raiz") if hallazgos_del else None,
            "confianza": hallazgos_del[0].get("confianza") if hallazgos_del else None,
            # --- qué propuso
            "accion_esperada": esperada.get("action_id"),
            "accion_propuesta": accion.get("action_id") if accion else None,
            "params_propuestos": accion.get("params") if accion else None,
            "accion_correcta": accion_correcta,
            # --- dónde se perdió, si se perdió
            "perdido_en": _donde_se_perdio(
                en_volcado, deteccion is not None, bool(hallazgos_del), accion is not None, esperada
            ),
        })
    return linaje


def _donde_se_perdio(
    lineas_en_volcado: int,
    detectado: bool,
    diagnosticado: bool,
    accionado: bool,
    esperada: dict[str, Any],
) -> str | None:
    """El primer salto donde el incidente dejó de avanzar. None si llegó al final.

    Sirve para leer el embudo al revés: no "cuántos se perdieron" sino "dónde".
    """
    if lineas_en_volcado == 0:
        return "recoleccion"
    if not detectado:
        return "triage"
    if not diagnosticado:
        return "especialista"
    if esperada.get("action_id") and not accionado:
        return "accion"
    return None


ETAPAS = [
    ("nacidos", "Incidentes vivos en el bus"),
    ("emitidos", "Publicados por al menos un canal"),
    ("recogidos", "Con líneas en el volcado del puente"),
    ("detectados", "Identificados por el triage"),
    ("tipo_correcto", "Con el tipo canónico correcto"),
    ("ruteo_correcto", "Ruteados al especialista correcto"),
    ("diagnosticados", "Con causa raíz de un especialista"),
    ("accionados", "Con acción correctiva propuesta"),
    ("accion_correcta", "Con la acción que esperaba el escenario"),
]


def construir_embudo(linaje: list[dict[str, Any]]) -> dict[str, Any]:
    """La conversión: cuántos incidentes sobreviven cada salto.

    Cada etapa se cuenta sobre el total de nacidos, y además contra la etapa
    anterior — que es donde se ve qué salto concreto pierde gente.
    """
    total = len(linaje)
    crudos = {
        "nacidos": total,
        "emitidos": sum(1 for f in linaje if f["canales_que_lo_publicaron"]),
        "recogidos": sum(1 for f in linaje if f["lineas_en_volcado"] > 0),
        "detectados": sum(1 for f in linaje if f["detectado"]),
        "tipo_correcto": sum(1 for f in linaje if f["tipo_correcto"]),
        "ruteo_correcto": sum(1 for f in linaje if f["ruteo_correcto"]),
        "diagnosticados": sum(1 for f in linaje if f["diagnosticado"]),
        "accionados": sum(1 for f in linaje if f["accion_propuesta"]),
        "accion_correcta": sum(1 for f in linaje if f["accion_correcta"]),
    }

    etapas = []
    anterior: int | None = None
    for clave, etiqueta in ETAPAS:
        valor = crudos[clave]
        etapas.append({
            "clave": clave,
            "etiqueta": etiqueta,
            "cantidad": valor,
            "sobre_total": round(valor / total, 4) if total else 0.0,
            "sobre_anterior": round(valor / anterior, 4) if anterior else (1.0 if anterior == 0 else None),
            "caida": (anterior - valor) if anterior is not None else 0,
        })
        anterior = valor

    perdidas: dict[str, int] = {}
    for fila in linaje:
        if fila["perdido_en"]:
            perdidas[fila["perdido_en"]] = perdidas.get(fila["perdido_en"], 0) + 1

    return {
        "total": total,
        "etapas": etapas,
        "conversion_global": round(crudos["diagnosticados"] / total, 4) if total else 0.0,
        "perdidas_por_salto": perdidas,
    }


def construir_ruido(
    verdad: dict[str, Any],
    triage: dict[str, Any] | None,
    canales: dict[str, Any],
) -> dict[str, Any]:
    """La otra mitad: lo que NO era incidente y el agente tuvo que descartar.

    Un agente que detecta todo lo real pero además inventa cinco incidentes no
    sirve. Los falsos positivos se cuentan aparte del embudo porque no nacen de
    ningún incidente: nacen de la nada.
    """
    indice = IndiceDeLineas(verdad)
    detecciones = (triage or {}).get("incidentes", [])
    atribuciones = [atribuir_deteccion(d, indice) for d in detecciones]
    falsos = [
        {"id": a["detectado_id"], "citas_no_ancladas": a["citas_no_ancladas"]}
        for a in atribuciones
        if a["falso_positivo"]
    ]
    descartados = (triage or {}).get("descartados", [])
    lineas_totales = sum(len(l) for l in canales.values() if l)
    return {
        "lineas_recogidas": lineas_totales,
        "detecciones_totales": len(detecciones),
        "falsos_positivos": len(falsos),
        "detalle_falsos_positivos": falsos,
        "descartes_declarados": len(descartados),
        "precision": round((len(detecciones) - len(falsos)) / len(detecciones), 4) if detecciones else None,
    }


def construir_por_pantalla(verdad: dict[str, Any], canales: dict[str, Any]) -> list[dict[str, Any]]:
    """Trazabilidad por pantalla: qué incidente vio cada canal y cuál se le pasó.

    `reportado_en` del bus dice qué canal publicó qué. Ningún canal reporta todo
    a propósito, así que "no lo publicó" es información, no un fallo.
    """
    activos = [i for i in verdad.get("incidentes", []) if not i.get("resuelto")]
    pantallas = [
        ("monitoreo", "Bus / feed de monitoreo", 8010),
        ("dev-chat", "Dev Chat", 8000),
        ("logs", "Semáforo y consola de logs", 8028),
        ("email-soporte", "Email de soporte", 8001),
    ]
    filas = []
    for clave, nombre, puerto in pantallas:
        publicados = [i["incidente_id"] for i in activos if clave in (i.get("reportado_en") or {})]
        recogidas = canales.get(clave)
        filas.append({
            "canal": clave,
            "pantalla": nombre,
            "puerto": puerto,
            "disponible": recogidas is not None,
            "lineas_recogidas": len(recogidas) if recogidas else 0,
            "incidentes_publicados": publicados,
            "incidentes_no_publicados": [
                i["incidente_id"] for i in activos if clave not in (i.get("reportado_en") or {})
            ],
            "cobertura": round(len(publicados) / len(activos), 4) if activos else None,
        })
    return filas


def trazar(
    verdad: dict[str, Any],
    canales: dict[str, Any],
    agente: dict[str, Any],
) -> dict[str, Any]:
    """El informe completo. Es lo que consume la pantalla de trazabilidad."""
    triage = agente.get("triage")
    hallazgos = agente.get("hallazgos", [])
    linaje = construir_linaje(verdad, triage, hallazgos, canales)
    return {
        "linaje": linaje,
        "embudo": construir_embudo(linaje),
        "ruido": construir_ruido(verdad, triage, canales),
        "por_pantalla": construir_por_pantalla(verdad, canales),
        "meta": agente.get("meta", {}),
    }
