#!/usr/bin/env python3
"""
Demo unificada en vivo.

4 paneles en tiempo real:
  1. Dev Chat — chat tipo Slack con hilos mezclados (charla + incidentes)
  2. Email — tickets de email llegando en vivo
  3. Monitoring Log — alertas firing/resolved en vivo
  4. Monitoring Dashboard — métricas visuales (gauges) de servicios

Panel inferior:
  5. Agent — cada señal que entra se procesa con el agente de triage
     (classify -> RAG -> consolidate) y aparece como incidente consolidado.

Todo via WebSocket. Un solo servidor, un solo frontend.

Uso:
    cd demo
    python -m uvicorn live_server:app --reload --port 8001
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
# El Agente 1 mantiene la cola de aprobaciones; este dashboard solo la refleja.
AGENTE_URL = os.environ.get("AGENTE_URL", "http://localhost:8080")
PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "channels" / "devchat" / "generator"))
sys.path.insert(0, str(PROJECT_ROOT / "channels" / "email" / "generator"))
sys.path.insert(0, str(PROJECT_ROOT / "channels" / "monitoring" / "generator"))

from generate_devchat_tickets import CATEGORIES as DEVCAT, CHANNELS, SERVICES as DEV_SERVICES, USERS, build_kb, weighted_choice
from generate_email_tickets import CATEGORIES as EMAILCAT, SERVICES as EMAIL_SERVICES, USERS as EMAIL_USERS, PRIORIDAD_POOL
from generate_monitoring_alerts import CATEGORIES as MONCAT, SERVICES as MON_SERVICES, ENVIRONMENTS

from agent.maas_client import MaaSClient, MaaSConfig
from agent.kb import KnowledgeBase
from agent.loop import triage
from agent.correlate import correlacionar, estadisticas
from agent.schema import Canal, SenalEntrante, IncidenteConsolidado

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("demo-live")

KB_PATH = PROJECT_ROOT / "channels" / "devchat" / "data" / "kb_incidentes_previos.jsonl"

app = FastAPI()

_ws_clients: set[WebSocket] = set()
_speed_mode = "normal"
_agent_enabled = False
_incidentes: list[IncidenteConsolidado] = []
_senal_counter = 0

SPEED_PRESETS = {
    "lento": (4.0, 8.0),
    "normal": (1.5, 4.0),
    "rapido": (0.5, 1.5),
}

SPEED_EMAIL = {"lento": (8.0, 16.0), "normal": (3.0, 8.0), "rapido": (1.0, 3.0)}
SPEED_MON = {"lento": (6.0, 12.0), "normal": (2.0, 6.0), "rapido": (0.5, 2.0)}

CHARLA_NORMAL = {
    "solicitud": {
        "weight": 0.28,
        "openers": [
            "alguien sabe como se configura el ambiente de {service} en local?",
            "necesito acceso al repo de {service}, quien lo administra?",
            "podemos agendar para revisar el diseno de {service}?",
            "quien puede revisarme este PR de {service}?",
            "hay doc actualizada de como se despliega {service}?",
        ],
        "followups": ["yo tengo la doc, te la paso", "listo, te agrego al repo", "dale, cuadremos para manana", "revisando, te dejo comentarios"],
    },
    "ruido": {
        "weight": 0.30,
        "openers": [
            "jajaja alguien vio el video que mande",
            "buen finde a todos!",
            "{service} volvio a la normalidad, era una alerta vieja, falsa alarma",
            "salio el deploy de {service}, todo verde",
            "alguien va a buscar cafe, se acepta pedido",
        ],
        "followups": ["dale, buen finde!", "ah ok gracias por avisar", "jajaj buenismo", "me sumo al cafe"],
    },
}


def _get_client() -> MaaSClient:
    return MaaSClient(MaaSConfig.from_env())


def _get_kb() -> KnowledgeBase:
    return KnowledgeBase(KB_PATH)


def _serialize_incidente(inc: IncidenteConsolidado) -> dict:
    d = inc.model_dump(mode="json")
    d["categoria"] = inc.categoria.value
    d["severidad"] = inc.severidad.value
    d["canal_origen"] = inc.canal_origen.value
    return d


async def _broadcast(msg: dict):
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.add(ws)
    _ws_clients -= dead


# ---------------------------------------------------------------------------
# Generador dev chat en vivo
# ---------------------------------------------------------------------------

class LiveDevChat:
    def __init__(self):
        self.kb = build_kb(15)
        self.active: list[dict] = []
        self._thread_counter = 0

    def _spawn_thread(self) -> dict:
        incident_weights = {c: DEVCAT[c]["weight"] for c in DEVCAT if DEVCAT[c]["es_incidente"]}
        pool = {**incident_weights, "solicitud": CHARLA_NORMAL["solicitud"]["weight"], "ruido": CHARLA_NORMAL["ruido"]["weight"]}
        category = weighted_choice(pool)

        if category in ("solicitud", "ruido"):
            cfg = CHARLA_NORMAL[category]
            es_incidente = False
            severidad = "n/a"
        else:
            cfg = DEVCAT[category]
            es_incidente = True
            severidad = weighted_choice(cfg["severidad_pool"])

        servicio = random.choice(DEV_SERVICES)
        participantes = random.sample(USERS, k=random.randint(2, 4))
        canal = random.choice(CHANNELS)
        self._thread_counter += 1
        thread_id = f"DC-LIVE-{self._thread_counter:04d}"

        ctx = {"service": servicio, "user": participantes[0][0], "user2": participantes[1][0], "hora": datetime.now().strftime("%H:%M")}

        queue = []
        queue.append((participantes[0], random.choice(cfg["openers"]).format(**ctx)))
        n_followups = random.randint(1, min(3, len(cfg["followups"])))
        for tmpl in random.sample(cfg["followups"], k=n_followups):
            queue.append((random.choice(participantes), tmpl.format(**ctx)))

        if es_incidente and "resolutions" in cfg and cfg["resolutions"] and random.random() < 0.45:
            queue.append((random.choice(participantes), random.choice(cfg["resolutions"]).format(**ctx)))

        return {
            "thread_id": thread_id,
            "canal": canal,
            "category": category,
            "es_incidente": es_incidente,
            "severidad": severidad,
            "servicio": servicio,
            "queue": queue,
            "emitted": 0,
        }


_live_chat = LiveDevChat()


async def devchat_loop():
    while True:
        lo, hi = SPEED_PRESETS[_speed_mode]
        await asyncio.sleep(random.uniform(lo, hi))

        room = len(_live_chat.active) < 5
        if room and (not _live_chat.active or random.random() < 0.45):
            _live_chat.active.append(_live_chat._spawn_thread())

        if not _live_chat.active:
            continue

        thread = random.choice(_live_chat.active)
        autor_tuple, texto = thread["queue"][thread["emitted"]]
        thread["emitted"] += 1
        now = datetime.now()

        msg = {
            "type": "devchat",
            "thread_id": thread["thread_id"],
            "canal": thread["canal"],
            "autor": autor_tuple[0],
            "rol": autor_tuple[1],
            "timestamp": now.isoformat(timespec="seconds"),
            "texto": texto,
            "is_last": thread["emitted"] == len(thread["queue"]),
            "thread_category": thread["category"],
            "thread_es_incidente": thread["es_incidente"],
            "thread_severidad": thread["severidad"],
            "thread_servicio": thread["servicio"],
        }
        await _broadcast(msg)

        if thread["emitted"] >= len(thread["queue"]):
            _live_chat.active.remove(thread)
            if _agent_enabled:
                await process_devchat_thread(thread)


async def process_devchat_thread(thread: dict):
    mensajes = thread["queue"]
    texto = " | ".join(f"@{a[0]}: {t}" for a, t in mensajes)
    global _senal_counter
    _senal_counter += 1
    senal = SenalEntrante(
        canal=Canal.devchat,
        id_externo=thread["thread_id"],
        timestamp=datetime.now(),
        servicio_afectado=thread["servicio"] if thread["es_incidente"] else None,
        texto=texto,
        metadata={"canal_chat": thread["canal"], "n_mensajes": len(mensajes)},
    )
    await run_agent(senal)


# ---------------------------------------------------------------------------
# Generador email en vivo
# ---------------------------------------------------------------------------

async def email_loop():
    while True:
        lo, hi = SPEED_EMAIL[_speed_mode]
        await asyncio.sleep(random.uniform(lo, hi))

        categorias = list(EMAILCAT.keys())
        pesos = [EMAILCAT[c]["weight"] for c in categorias]
        category = random.choices(categorias, weights=pesos, k=1)[0]
        cfg = EMAILCAT[category]

        servicio = random.choice(EMAIL_SERVICES)
        remitente = random.choice(EMAIL_USERS)
        t0 = datetime.now()
        ctx = {"service": servicio, "hora": t0.strftime("%H:%M")}

        subject = random.choice(cfg["subjects"]).format(**ctx)
        body = random.choice(cfg["bodies"]).format(**ctx)
        severidad = weighted_choice(cfg["severidad_pool"]) if cfg["es_incidente"] else "n/a"
        prioridad = weighted_choice(PRIORIDAD_POOL)

        global _senal_counter
        _senal_counter += 1
        ticket_id = f"EM-LIVE-{_senal_counter:04d}"

        event = {
            "type": "email",
            "id": ticket_id,
            "timestamp": t0.isoformat(timespec="seconds"),
            "subject": subject,
            "body": body[:200],
            "remitente": remitente[0],
            "prioridad_declarada": prioridad,
            "servicio_afectado": servicio if cfg["es_incidente"] else None,
            "categoria_real": category,
            "es_incidente": cfg["es_incidente"],
            "severidad_real": severidad,
        }
        await _broadcast(event)

        if _agent_enabled:
            senal = SenalEntrante(
                canal=Canal.email,
                id_externo=ticket_id,
                timestamp=t0,
                servicio_afectado=servicio if cfg["es_incidente"] else None,
                texto=f"Subject: {subject}\n\n{body}",
                metadata={"remitente": remitente[0], "prioridad_declarada": prioridad, "tipo_remitente": remitente[1]},
            )
            await run_agent(senal)


# ---------------------------------------------------------------------------
# Generador monitoring en vivo
# ---------------------------------------------------------------------------

_monitoring_metrics: dict[str, dict] = {}

async def monitoring_loop():
    while True:
        lo, hi = SPEED_MON[_speed_mode]
        await asyncio.sleep(random.uniform(lo, hi))

        categorias = list(MONCAT.keys())
        pesos = [MONCAT[c]["weight"] for c in categorias]
        category = random.choices(categorias, weights=pesos, k=1)[0]
        cfg = MONCAT[category]

        servicio = random.choice(MON_SERVICES)
        env = random.choice(ENVIRONMENTS)
        t0 = datetime.now()

        alert_name = random.choice(cfg["alert_names"])
        metric_name, metric_value, threshold, desc_template = random.choice(cfg["metrics"])
        description = desc_template.format(service=servicio, value=metric_value)

        if category == "ruido":
            alert_state = "resolved"
            es_incidente = False
            severidad = "n/a"
        else:
            alert_state = "firing"
            es_incidente = True
            severidad = weighted_choice(cfg["severidad_pool"])

        global _senal_counter
        _senal_counter += 1
        alert_id = f"AL-LIVE-{_senal_counter:04d}"

        if servicio not in _monitoring_metrics:
            _monitoring_metrics[servicio] = {"health": "healthy", "latency": 250, "error_rate": 0.01, "disk": 45}
        if alert_state == "firing":
            if "Latency" in alert_name or "latency" in metric_name:
                _monitoring_metrics[servicio]["latency"] = int(metric_value)
            elif "Disk" in alert_name or "disk" in metric_name:
                _monitoring_metrics[servicio]["disk"] = int(metric_value)
            elif "error" in metric_name.lower():
                _monitoring_metrics[servicio]["error_rate"] = round(metric_value, 2)
            _monitoring_metrics[servicio]["health"] = "unhealthy"
        else:
            _monitoring_metrics[servicio]["health"] = "healthy"
            _monitoring_metrics[servicio]["latency"] = random.randint(200, 400)
            _monitoring_metrics[servicio]["error_rate"] = round(random.uniform(0.005, 0.02), 3)
            _monitoring_metrics[servicio]["disk"] = random.randint(30, 60)

        event = {
            "type": "monitoring",
            "id": alert_id,
            "timestamp": t0.isoformat(timespec="seconds"),
            "alert_name": alert_name,
            "alert_state": alert_state,
            "servicio_afectado": servicio if es_incidente else None,
            "environment": env,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "metric_threshold": threshold,
            "description": description,
            "severidad_real": severidad,
            "categoria_real": category,
            "es_incidente": es_incidente,
        }
        await _broadcast(event)

        await _broadcast({"type": "dashboard", "metrics": dict(_monitoring_metrics)})

        if _agent_enabled and es_incidente:
            texto = (
                f"Alert: {alert_name} on {servicio} ({env})\n"
                f"State: {alert_state}\n"
                f"Metric: {metric_name}={metric_value} (threshold {threshold})\n"
                f"Description: {description}"
            )
            senal = SenalEntrante(
                canal=Canal.monitoring,
                id_externo=alert_id,
                timestamp=t0,
                servicio_afectado=servicio,
                texto=texto,
                metadata={"alert_name": alert_name, "alert_state": alert_state, "environment": env, "metric_name": metric_name, "metric_value": metric_value, "metric_threshold": threshold},
            )
            await run_agent(senal)


# ---------------------------------------------------------------------------
# Agente
# ---------------------------------------------------------------------------

async def run_agent(senal: SenalEntrante):
    await _broadcast({"type": "agent_start", "canal": senal.canal.value, "id_externo": senal.id_externo})
    try:
        client = _get_client()
        kb = _get_kb()
        inc = await asyncio.to_thread(triage, senal, client, kb)
        _incidentes.append(inc)

        correlacionar(_incidentes)
        serialized = _serialize_incidente(inc)

        all_serialized = [_serialize_incidente(i) for i in _incidentes]
        stats = estadisticas(_incidentes)

        await _broadcast({"type": "agent_result", "incidente": serialized, "all_incidentes": all_serialized, "stats": stats})
    except Exception as e:
        logger.error("agent error on %s: %s", senal.id_externo, e)
        await _broadcast({"type": "agent_error", "id_externo": senal.id_externo, "error": str(e)})


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(devchat_loop())
    asyncio.create_task(email_loop())
    asyncio.create_task(monitoring_loop())
    logger.info("demo-live started — generadores devchat + email + monitoring corriendo")


@app.get("/")
async def index():
    html = (BASE_DIR / "static" / "live.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.post("/api/agent/toggle")
async def toggle_agent():
    global _agent_enabled
    _agent_enabled = not _agent_enabled
    await _broadcast({"type": "agent_status", "enabled": _agent_enabled})
    return {"enabled": _agent_enabled}


@app.get("/api/agent/status")
async def agent_status():
    return {"enabled": _agent_enabled}


@app.post("/api/speed")
async def set_speed(payload: dict):
    global _speed_mode
    _speed_mode = payload.get("mode", "normal")
    await _broadcast({"type": "speed", "mode": _speed_mode})
    return {"speed_mode": _speed_mode}


@app.get("/api/aprobaciones")
async def listar_aprobaciones():
    """Proxy a la cola del Agente 1. Va por el servidor y no desde el navegador
    para no depender de que el otro puerto habilite CORS."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"{AGENTE_URL}/api/aprobaciones")
            res.raise_for_status()
            cuerpo = res.json()
            # El Agente 1 devuelve la lista anidada junto a metadatos de la corrida.
            lista = cuerpo.get("aprobaciones", []) if isinstance(cuerpo, dict) else cuerpo
            return {"aprobaciones": lista, "disponible": True}
    except Exception as e:
        return {"aprobaciones": [], "disponible": False, "error": str(e)[:120]}


@app.post("/api/aprobaciones/{aprobacion_id}")
async def decidir_aprobacion(aprobacion_id: str, payload: dict):
    """Aprobar o rechazar. Es el único punto donde una acción propuesta por el
    agente puede pasar a ejecutarse: siempre con un humano de por medio."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                f"{AGENTE_URL}/api/aprobaciones/{aprobacion_id}",
                json={"decision": payload.get("decision"),
                      "actor": payload.get("actor", "operador-demo"),
                      "nota": payload.get("nota", "")},
            )
            return {"ok": res.status_code == 200, "respuesta": res.json()}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


@app.get("/api/stats")
async def get_stats():
    return estadisticas(_incidentes) if _incidentes else {}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    await websocket.send_json({"type": "agent_status", "enabled": _agent_enabled})
    await websocket.send_json({"type": "speed", "mode": _speed_mode})
    if _monitoring_metrics:
        await websocket.send_json({"type": "dashboard", "metrics": dict(_monitoring_metrics)})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(websocket)


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
