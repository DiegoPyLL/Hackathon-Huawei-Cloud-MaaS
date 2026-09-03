#!/usr/bin/env python3
"""
Simulador de dev chat en vivo.

Corre varios "hilos" (charla normal e incidentes) en paralelo y los va
intercalando mensaje a mensaje, como pasaría en un chat real con varias
conversaciones abiertas a la vez. Sirve un frontend tipo Slack por HTTP y
empuja los mensajes nuevos por WebSocket.

Dos salidas separadas a propósito:
  - Feed público (WS + /api/history + devchat_live_public.jsonl): solo
    canal/autor/rol/timestamp/texto. Es lo único que ve el chat y lo único
    que va a leer el agente de triage — sin thread_id ni categoría ni
    severidad, para no regalarle el trabajo de clasificar/correlacionar.
  - Log de groundtruth (devchat_live_groundtruth.jsonl + /api/stats): la
    verdad completa (categoria_real, es_incidente, severidad_real,
    thread_id) más contadores corriendo. No se transmite nunca al frontend,
    es solo para medir después qué tan bien clasificó el agente.

Uso:
    uvicorn server:app --reload --port 8000
"""

import asyncio
import copy
import json
import random
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "generator"))
from generate_devchat_tickets import (  # noqa: E402
    CATEGORIES,
    CHANNELS,
    SERVICES,
    USERS,
    build_kb,
    weighted_choice,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
PUBLIC_LOG = DATA_DIR / "devchat_live_public.jsonl"
GROUNDTRUTH_LOG = DATA_DIR / "devchat_live_groundtruth.jsonl"

PUBLIC_FIELDS = ("seq", "canal", "autor", "rol", "timestamp", "texto")

MAX_ACTIVE_THREADS = 5
P_SPAWN_NEW = 0.45
HISTORY_BUFFER = 300

SPEED_PRESETS = {
    "lento": (4.0, 8.0),
    "normal": (1.5, 4.0),
    "rapido": (0.5, 1.5),
}

# --------------------------------------------------------------------------
# Vocabulario extra de "charla normal" — no forma parte de la taxonomía de
# incidentes, cae en los buckets solicitud/ruido, pero con más variedad que
# los 3 templates del generador batch para que el chat se sienta vivo.
# --------------------------------------------------------------------------

CHARLA_NORMAL = {
    "solicitud": {
        "weight": 0.28,
        "es_incidente": False,
        "openers": [
            "alguien sabe cómo se configura el ambiente de {service} en local?",
            "necesito acceso al repo de {service}, quién lo administra?",
            "podemos agendar para revisar el diseño de {service}?",
            "quién puede revisarme este PR de {service} cuando tenga un rato?",
            "hay doc actualizada de cómo se despliega {service}?",
            "alguien libre para pairear un rato en {service}?",
            "puedo mergear el PR de {service} o falta algo?",
            "a qué hora es el standup hoy?",
            "alguien tiene el dashboard de {service} a mano?",
        ],
        "followups": [
            "yo tengo la doc, te la paso",
            "listo, te agrego al repo",
            "dale, cuadremos para mañana",
            "revisando, te dejo comentarios en un rato",
            "aprobado, buen trabajo",
            "en 10 min arrancamos",
            "te paso el link por privado",
        ],
        "resolutions": [],
    },
    "ruido": {
        "weight": 0.30,
        "es_incidente": False,
        "openers": [
            "jajaja alguien vio el video que mandé",
            "buen finde a todos!",
            "{service} volvió a la normalidad, era una alerta vieja, falsa alarma",
            "salió el deploy de {service}, todo verde ✅",
            "feliz cumple {user2}! 🎉",
            "alguien va a buscar café, se acepta pedido",
            "terminamos el sprint, buen laburo equipo",
            "recordatorio: mañana no hay daily, hay retro a las 10",
            "subieron las métricas del mes, {service} viene mejor que el anterior",
            "alguien probó el nuevo panel de {service}? se ve bien",
        ],
        "followups": [
            "dale, buen finde!",
            "ah ok gracias por avisar",
            "jajaj buenísimo",
            "gracias equipo 🙌",
            "anotado",
            "me sumo al café",
        ],
        "resolutions": [],
    },
}


def build_charla_cfg(category: str) -> dict:
    cfg = copy.deepcopy(CHARLA_NORMAL[category])
    cfg["severidad_pool"] = {}
    return cfg


# --------------------------------------------------------------------------
# Motor de hilos concurrentes
# --------------------------------------------------------------------------


class LiveThread:
    def __init__(self, thread_id: str, category: str, cfg: dict, kb: list):
        self.thread_id = thread_id
        self.category = category
        self.es_incidente = cfg["es_incidente"]
        self.canal = random.choice(CHANNELS)
        self.servicio = random.choice(SERVICES)
        self.participantes = random.sample(USERS, k=random.randint(2, 4))
        self.severidad = weighted_choice(cfg["severidad_pool"]) if cfg.get("severidad_pool") else "n/a"
        self.tono = random.choices(["urgente", "neutral", "casual"], weights=[0.35, 0.4, 0.25], k=1)[0]
        self.deploy_relacionado = self.es_incidente and random.random() < 0.25
        self.menciona_prev = False
        self.id_prev = None

        ctx = {
            "service": self.servicio,
            "user": self.participantes[0][0],
            "user2": self.participantes[1][0] if len(self.participantes) > 1 else self.participantes[0][0],
            "hora": datetime.now().strftime("%H:%M"),
        }

        queue = []
        autor_principal = self.participantes[0]
        queue.append((autor_principal, random.choice(cfg["openers"]).format(**ctx)))

        n_followups = random.randint(1, min(4, len(cfg["followups"])))
        for tmpl in random.sample(cfg["followups"], k=n_followups):
            autor = random.choice(self.participantes)
            queue.append((autor, tmpl.format(**ctx)))

        if self.es_incidente and kb and random.random() < 0.3:
            candidatos = [k for k in kb if k["servicio"] == self.servicio] or kb
            prev = random.choice(candidatos)
            self.id_prev, self.menciona_prev = prev["id"], True
            autor = random.choice(self.participantes)
            queue.append((autor, f"esto me suena a {prev['id']}, {prev['resumen']}"))

        self.resuelto = False
        if cfg.get("resolutions") and random.random() < 0.45:
            autor = random.choice(self.participantes)
            queue.append((autor, random.choice(cfg["resolutions"]).format(**ctx)))
            self.resuelto = True

        self.queue = queue
        self.emitted = 0

    def has_next(self) -> bool:
        return self.emitted < len(self.queue)

    def next_message(self) -> dict:
        autor_tuple, texto = self.queue[self.emitted]
        self.emitted += 1
        now = datetime.now()
        return {
            "thread_id": self.thread_id,
            "canal": self.canal,
            "autor": autor_tuple[0],
            "rol": autor_tuple[1],
            "timestamp": now.isoformat(timespec="seconds"),
            "texto": texto,
            "categoria_real": self.category,
            "es_incidente": self.es_incidente,
            "severidad_real": self.severidad,
            "tono_percibido": self.tono,
            "servicio_afectado": self.servicio if self.es_incidente else None,
            "deploy_relacionado": self.deploy_relacionado,
            "menciona_incidente_previo": self.menciona_prev,
            "id_incidente_previo_referenciado": self.id_prev,
            "thread_msg_index": self.emitted,
            "thread_msg_count_planned": len(self.queue),
            "thread_resuelto": self.resuelto and self.emitted == len(self.queue),
        }


class ChatEngine:
    def __init__(self):
        self.kb = build_kb(15)
        self.active: list[LiveThread] = []
        self.seq = 0
        self.speed_mode = "normal"
        self.connections: set[WebSocket] = set()
        self.history: list[dict] = []
        self._thread_counter = 0
        self._task: asyncio.Task | None = None

        self.stats = {
            "inicio": datetime.now().isoformat(timespec="seconds"),
            "total_mensajes": 0,
            "total_mensajes_incidente": 0,
            "total_mensajes_normales": 0,
            "total_hilos": 0,
            "hilos_incidente": 0,
            "hilos_normales": 0,
            "hilos_por_categoria": {},
            "hilos_por_severidad": {},
        }

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._public_log = open(PUBLIC_LOG, "w", encoding="utf-8")
        self._groundtruth_log = open(GROUNDTRUTH_LOG, "w", encoding="utf-8")

    def _spawn_thread(self):
        incident_weights = {c: CATEGORIES[c]["weight"] for c in CATEGORIES if CATEGORIES[c]["es_incidente"]}
        pool = {**incident_weights, "solicitud": CHARLA_NORMAL["solicitud"]["weight"], "ruido": CHARLA_NORMAL["ruido"]["weight"]}
        category = weighted_choice(pool)

        if category in ("solicitud", "ruido"):
            cfg = build_charla_cfg(category)
        else:
            cfg = CATEGORIES[category]

        self._thread_counter += 1
        thread_id = f"DEVCHAT-LIVE-{self._thread_counter:04d}"
        thread = LiveThread(thread_id, category, cfg, self.kb)
        self.active.append(thread)

        self.stats["total_hilos"] += 1
        if thread.es_incidente:
            self.stats["hilos_incidente"] += 1
            self.stats["hilos_por_severidad"][thread.severidad] = self.stats["hilos_por_severidad"].get(thread.severidad, 0) + 1
        else:
            self.stats["hilos_normales"] += 1
        self.stats["hilos_por_categoria"][category] = self.stats["hilos_por_categoria"].get(category, 0) + 1

    async def _broadcast(self, message: dict):
        dead = set()
        for ws in self.connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        self.connections -= dead

    def _persist(self, full_message: dict, public_message: dict):
        self._groundtruth_log.write(json.dumps(full_message, ensure_ascii=False) + "\n")
        self._groundtruth_log.flush()
        self._public_log.write(json.dumps(public_message, ensure_ascii=False) + "\n")
        self._public_log.flush()

        self.history.append(public_message)
        if len(self.history) > HISTORY_BUFFER:
            self.history.pop(0)

        self.stats["total_mensajes"] += 1
        if full_message["es_incidente"]:
            self.stats["total_mensajes_incidente"] += 1
        else:
            self.stats["total_mensajes_normales"] += 1

    async def run(self):
        while True:
            lo, hi = SPEED_PRESETS[self.speed_mode]
            await asyncio.sleep(random.uniform(lo, hi))

            room = len(self.active) < MAX_ACTIVE_THREADS
            if room and (not self.active or random.random() < P_SPAWN_NEW):
                self._spawn_thread()

            if not self.active:
                continue

            thread = random.choice(self.active)
            full_message = thread.next_message()
            self.seq += 1
            full_message["seq"] = self.seq
            public_message = {k: full_message[k] for k in PUBLIC_FIELDS}

            self._persist(full_message, public_message)
            await self._broadcast(public_message)

            if not thread.has_next():
                self.active.remove(thread)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    def set_speed(self, mode: str):
        if mode in SPEED_PRESETS:
            self.speed_mode = mode


engine = ChatEngine()
app = FastAPI()


@app.on_event("startup")
async def on_startup():
    engine.start()


@app.get("/")
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/channels")
async def get_channels():
    return {"channels": CHANNELS}


@app.get("/api/history")
async def get_history(limit: int = 50, channel: str | None = None):
    items = engine.history
    if channel:
        items = [m for m in items if m["canal"] == channel]
    return {"messages": items[-limit:]}


@app.post("/api/speed")
async def set_speed(payload: dict):
    engine.set_speed(payload.get("mode", "normal"))
    return {"speed_mode": engine.speed_mode}


@app.get("/api/stats")
async def get_stats():
    """Groundtruth de monitoreo — no linkeado desde la UI del chat. Cuenta
    la realidad (mensajes/hilos, incidente vs normal) para medir después
    contra lo que detecte el agente."""
    return engine.stats


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    engine.connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        engine.connections.discard(websocket)


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
