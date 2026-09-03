"""
Tools del agente de triage.

El agente tiene dos tools:
  1. classify_incident — clasifica una señal entrante contra la taxonomía.
  2. search_similar_incidents — busca en la KB incidentes previos similares.

El loop orquesta: classify → search_similar → consolidate.
"""

from __future__ import annotations

import json
from typing import Any

from .maas_client import MaaSClient
from .schema import Categoria, Canal, Severidad, SenalEntrante
from .kb import KnowledgeBase


CLASSIFY_SYSTEM = """\
Eres un clasificador de incidentes de sistemas. Recibes una señal de un canal
(email, monitoring o dev chat) y debes clasificarla.

Taxonomía canónica (8 tipos de incidente + 2 buckets que no son incidente):
1. indisponibilidad — servicio caído, endpoint no responde
2. degradacion — latencia, timeouts, lentitud
3. error_funcional — bug, cálculo incorrecto, flujo roto
4. acceso_identidad — login, permisos, MFA, cuenta bloqueada
5. datos — faltantes, incorrectos, sincronización fallida
6. integracion_terceros — API externa, webhook, pasarela de pago
7. capacidad — disco, memoria, cuota, rate limit
8. seguridad — actividad sospechosa, credencial expuesta, phishing
9. solicitud — consulta, how-to, feature request, cambio (NO es incidente)
10. ruido — duplicado, alerta ya recuperada, conversación sin incidente (NO es incidente)

REGLAS CRÍTICAS:
- La severidad se calcula por IMPACTO REAL, no por el tono del mensaje ni la
  prioridad declarada. Un mensaje urgente puede ser severidad baja; un mensaje
  tranquilo puede describir un corte total.
- Si la señal es una alerta con state=resolved, es ruido (ya se recuperó).
- Si no hay evidencia de un problema de producción, clasifica como solicitud o ruido.

Devuelve SOLO JSON con este esquema exacto:
{
  "categoria": "<una de las 10 categorías>",
  "es_incidente": true/false,
  "severidad": "critica|alta|media|baja|n/a",
  "servicio_afectado": "<string o null>",
  "resumen": "<resumen ejecutivo 1-2 frases>",
  "causa_raiz_probable": "<string o null>",
  "confianza": <float 0.0-1.0>
}
"""


def build_senal_text(senal: SenalEntrante) -> str:
    parts = [f"[Canal: {senal.canal.value}]"]
    if senal.servicio_afectado:
        parts.append(f"[Servicio: {senal.servicio_afectado}]")
    for k, v in senal.metadata.items():
        if k != "texto":
            parts.append(f"[{k}: {v}]")
    parts.append(senal.texto)
    return "\n".join(parts)


def classify_incident(client: MaaSClient, senal: SenalEntrante) -> dict[str, Any]:
    user_msg = build_senal_text(senal)
    messages = [
        {"role": "system", "content": CLASSIFY_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    result = client.chat_json(messages, model=client.config.model_cheap, temperature=0.1)
    return result


def search_similar_incidents(
    kb: KnowledgeBase,
    query: str,
    servicio: str | None = None,
    categoria: Categoria | None = None,
    top_k: int = 3,
) -> list[dict]:
    refs = kb.search(query=query, servicio=servicio, categoria=categoria, top_k=top_k)
    return [r.model_dump() for r in refs]


CONSOLIDATE_SYSTEM = """\
Eres un agente de triage de incidentes. Recibes la clasificación inicial de una
señal y los incidentes previos similares encontrados en la base de conocimiento.

Tu trabajo es producir el incidente consolidado final:
- Un resumen ejecutivo claro (1-2 frases).
- La causa raíz probable, apoyándote en incidentes previos si hay.
- Acciones recomendadas concretas y accionables.
- Si hay incidentes previos muy similares, mencionar cómo se resolvió antes.

Devuelve SOLO JSON:
{
  "resumen": "<string>",
  "causa_raiz_probable": "<string o null>",
  "acciones_recomendadas": ["<string>", ...],
  "confianza": <float 0.0-1.0>
}
"""


def consolidate(
    client: MaaSClient,
    clasificacion: dict,
    incidentes_previos: list[dict],
    senal: SenalEntrante,
) -> dict[str, Any]:
    context = {
        "clasificacion": clasificacion,
        "incidentes_previos_similares": incidentes_previos,
        "canal_origen": senal.canal.value,
        "texto_original": senal.texto[:500],
    }
    messages = [
        {"role": "system", "content": CONSOLIDATE_SYSTEM},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False, indent=2)},
    ]
    result = client.chat_json(messages, model=client.config.model_strong, temperature=0.2)
    return result
