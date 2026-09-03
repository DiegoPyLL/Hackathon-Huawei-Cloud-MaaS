#!/usr/bin/env python3
"""
Demo UI del agente de triage.

Carga señales de los tres canales, las procesa con el agente, y sirve una
UI web donde se ven los incidentes consolidados en tiempo real.

Endpoints:
  GET  /              — UI web
  GET  /api/senales   — señales cargadas (sin triage)
  POST /api/triage    — ejecuta el agente sobre todas las señales
  GET  /api/incidentes — resultados del triage (incidentes consolidados)
  GET  /api/stats     — estadísticas de correlación/deduplicación
  WS   /ws            — stream de incidentes en tiempo real durante el triage

Uso:
    cd demo
    python -m uvicorn server:app --reload --port 8001
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))

from agent.load_senales import load_all
from agent.maas_client import MaaSClient, MaaSConfig
from agent.kb import KnowledgeBase
from agent.loop import triage
from agent.correlate import correlacionar, estadisticas
from agent.schema import IncidenteConsolidado

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("demo")

KB_PATH = PROJECT_ROOT / "channels" / "devchat" / "data" / "kb_incidentes_previos.jsonl"

app = FastAPI()

_state: dict = {
    "senales": [],
    "incidentes": [],
    "stats": {},
    "processing": False,
}
_ws_clients: set[WebSocket] = set()


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


@app.on_event("startup")
async def on_startup():
    senales = load_all(PROJECT_ROOT)
    _state["senales"] = [
        {
            "canal": s.canal.value,
            "id_externo": s.id_externo,
            "timestamp": s.timestamp.isoformat(),
            "servicio_afectado": s.servicio_afectado,
            "texto_preview": s.texto[:200],
            "metadata": s.metadata,
        }
        for s in senales
    ]
    logger.info("cargadas %d señales", len(senales))


@app.get("/")
async def index():
    html = (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/senales")
async def get_senales():
    return {"senales": _state["senales"], "total": len(_state["senales"])}


@app.get("/api/incidentes")
async def get_incidentes():
    return {"incidentes": _state["incidentes"], "total": len(_state["incidentes"])}


@app.get("/api/stats")
async def get_stats():
    return _state["stats"]


@app.post("/api/triage")
async def run_triage():
    if _state["processing"]:
        return JSONResponse({"error": "ya hay un triage corriendo"}, status_code=409)

    _state["processing"] = True
    _state["incidentes"] = []
    _state["stats"] = {}

    try:
        client = _get_client()
        kb = _get_kb()
        senales = load_all(PROJECT_ROOT)
        logger.info("iniciando triage de %d señales", len(senales))

        incidentes: list[IncidenteConsolidado] = []
        for i, senal in enumerate(senales):
            try:
                inc = triage(senal, client, kb)
                serialized = _serialize_incidente(inc)
                _state["incidentes"].append(serialized)

                await _broadcast({"type": "incidente", "data": serialized, "progress": i + 1, "total": len(senales)})
            except Exception as e:
                logger.error("error en triage de %s: %s", senal.id_externo, e)
                await _broadcast({"type": "error", "id": senal.id_externo, "error": str(e), "progress": i + 1, "total": len(senales)})

        incidentes_correl = correlacionar(incidentes)
        _state["incidentes"] = [_serialize_incidente(i) for i in incidentes_correl]
        _state["stats"] = estadisticas(incidentes_correl)

        await _broadcast({"type": "done", "stats": _state["stats"]})
        logger.info("triage completo: %s", _state["stats"])
        return {"ok": True, "total": len(incidentes_correl), "stats": _state["stats"]}
    except Exception as e:
        logger.error("error fatal en triage: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        _state["processing"] = False


async def _broadcast(msg: dict):
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.add(ws)
    _ws_clients -= dead


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(websocket)


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
