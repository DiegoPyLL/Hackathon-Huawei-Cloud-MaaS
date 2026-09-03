"""
Loop del agente de triage.

Flujo:
  1. Recibe una SenalEntrante (de cualquier canal).
  2. classify_incident → clasifica contra la taxonomía (modelo barato).
  3. search_similar_incidents → busca en KB (RAG, sin LLM).
  4. consolidate → resumen ejecutivo + recomendación (modelo fuerte).
  5. Devuelve IncidenteConsolidado.

Un agente, un loop, pocas tools. No multiagente.
"""

from __future__ import annotations

import itertools
import logging
from datetime import datetime

from .maas_client import MaaSClient
from .kb import KnowledgeBase
from .schema import (
    Categoria,
    Canal,
    IncidenteConsolidado,
    IncidentePrevioRef,
    SenalEntrante,
    Severidad,
    dueño_sugerido,
)
from .tools import classify_incident, search_similar_incidents, consolidate

logger = logging.getLogger("agent")

_id_counter = itertools.count(1)


def _next_id() -> str:
    return f"INC-AGENT-{next(_id_counter):04d}"


def _safe_categoria(val: str) -> Categoria:
    try:
        return Categoria(val)
    except ValueError:
        return Categoria.ruido


def _safe_severidad(val: str) -> Severidad:
    try:
        return Severidad(val)
    except ValueError:
        return Severidad.n_a


def triage(
    senal: SenalEntrante,
    client: MaaSClient,
    kb: KnowledgeBase,
) -> IncidenteConsolidado:
    logger.info("triage start: canal=%s id=%s", senal.canal.value, senal.id_externo)

    clasificacion = classify_incident(client, senal)
    logger.info("classified: %s", clasificacion.get("categoria"))

    categoria = _safe_categoria(clasificacion.get("categoria", "ruido"))
    severidad = _safe_severidad(clasificacion.get("severidad", "n/a"))
    es_incidente = clasificacion.get("es_incidente", False)
    servicio = clasificacion.get("servicio_afectado") or senal.servicio_afectado
    confianza = float(clasificacion.get("confianza", 0.5))

    incidentes_previos: list[IncidentePrevioRef] = []
    if es_incidente:
        raw_refs = search_similar_incidents(
            kb,
            query=senal.texto,
            servicio=servicio,
            categoria=categoria,
            top_k=3,
        )
        incidentes_previos = [IncidentePrevioRef(**r) for r in raw_refs]

    consolidation = consolidate(client, clasificacion, [r.model_dump() for r in incidentes_previos], senal)
    logger.info("consolidated: confianza=%s", consolidation.get("confianza"))

    resumen = consolidation.get("resumen", clasificacion.get("resumen", ""))
    causa_raiz = consolidation.get("causa_raiz_probable") or clasificacion.get("causa_raiz_probable")
    acciones = consolidation.get("acciones_recomendadas", [])
    confianza_final = min(confianza, float(consolidation.get("confianza", confianza)))

    incidente = IncidenteConsolidado(
        id=_next_id(),
        canal_origen=senal.canal,
        id_externo=senal.id_externo,
        categoria=categoria,
        es_incidente=es_incidente,
        severidad=severidad,
        servicio_afectado=servicio,
        resumen=resumen,
        causa_raiz_probable=causa_raiz,
        acciones_recomendadas=acciones,
        incidentes_previos_similares=incidentes_previos,
        dueño_sugerido=dueño_sugerido(categoria) if es_incidente else None,
        confianza=confianza_final,
        timestamp=senal.timestamp,
        metadata={"canal_raw": senal.metadata},
    )

    logger.info("triage done: %s incidente=%s sev=%s", incidente.id, incidente.es_incidente, incidente.severidad.value)
    return incidente
