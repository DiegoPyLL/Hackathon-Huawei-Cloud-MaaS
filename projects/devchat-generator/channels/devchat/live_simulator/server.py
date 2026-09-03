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
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
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

# Ningún sistema de mensajería real deja sus endpoints abiertos: el feed exige
# token, igual que haría falta un token de bot para leer Slack de verdad.
API_TOKEN = os.environ.get("DEVCHAT_API_TOKEN", "devchat-dev-token")

# Fuente de verdad de qué incidentes están pasando (projects/bus-incidentes).
BUS_URL = os.environ.get("BUS_URL", "http://localhost:8010")
# Parte de los incidentes nunca se comenta en el chat, aunque sí salgan en
# monitoreo y en el semáforo.
P_REPORTAR_EN_CHAT = 0.8


def require_token(authorization: str = Header(default="")):
    if authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="token inválido o faltante")

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
    def __init__(self, thread_id: str, category: str, cfg: dict, kb: list, incidente: dict | None = None):
        self.thread_id = thread_id
        self.category = category
        self.es_incidente = cfg["es_incidente"]
        self.canal = random.choice(CHANNELS)
        # Si el hilo viene del bus, el servicio y la severidad los dicta el
        # incidente real — es lo que permite correlacionarlo con monitoreo y el
        # semáforo. Si no, el hilo es charla local y se inventa lo suyo.
        self.incidente_id = incidente["incidente_id"] if incidente else None
        self.servicio = incidente["servicio"] if incidente else random.choice(SERVICES)
        self.participantes = random.sample(USERS, k=random.randint(2, 4))
        if incidente:
            self.severidad = incidente["severidad"]
        else:
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
            "incidente_id": self.incidente_id,
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

        self.incidentes_bus: list[dict] = []
        self._incidentes_vistos: set[str] = set()
        self.bus_conectado = False

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
            "incidentes_bus_reportados": 0,
            "incidentes_bus_no_reportados": 0,
        }

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._public_log = open(PUBLIC_LOG, "w", encoding="utf-8")
        self._groundtruth_log = open(GROUNDTRUTH_LOG, "w", encoding="utf-8")

    def _spawn_thread(self):
        # Primero se mira si el bus tiene un incidente real que el chat todavía
        # no comentó. Si lo hay, el hilo habla de ESE incidente; si no, se genera
        # charla local (solicitud/ruido), que no necesita correlacionarse.
        incidente = self._tomar_incidente_pendiente()

        if incidente:
            category = incidente["tipo"].replace("-", "_")
            cfg = CATEGORIES.get(category)
            if cfg is None:
                incidente = None

        if not incidente:
            category = weighted_choice({
                "solicitud": CHARLA_NORMAL["solicitud"]["weight"],
                "ruido": CHARLA_NORMAL["ruido"]["weight"],
            })
            cfg = build_charla_cfg(category)

        self._thread_counter += 1
        thread_id = f"DEVCHAT-LIVE-{self._thread_counter:04d}"
        thread = LiveThread(thread_id, category, cfg, self.kb, incidente=incidente)
        self.active.append(thread)

        self.stats["total_hilos"] += 1
        if thread.es_incidente:
            self.stats["hilos_incidente"] += 1
            self.stats["hilos_por_severidad"][thread.severidad] = self.stats["hilos_por_severidad"].get(thread.severidad, 0) + 1
        else:
            self.stats["hilos_normales"] += 1
        self.stats["hilos_por_categoria"][category] = self.stats["hilos_por_categoria"].get(category, 0) + 1

        if incidente:
            self.stats["incidentes_bus_reportados"] += 1
            asyncio.create_task(self._avisar_al_bus(incidente["incidente_id"]))

    async def _avisar_al_bus(self, incidente_id: str):
        """Le dice al bus que este canal ya reportó el incidente, para que la
        vista de correlación sepa por dónde entró cada señal."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(
                    f"{BUS_URL}/api/incidentes/{incidente_id}/reportado",
                    json={"canal": "dev-chat"},
                )
        except Exception:
            pass

    def _tomar_incidente_pendiente(self) -> dict | None:
        """Devuelve un incidente del bus que este chat todavía no comentó.

        A propósito no se reporta todo: una parte de los incidentes nunca se
        menciona en el chat aunque sí aparezca en monitoreo y en el semáforo.
        Esa asimetría es la que obliga al agente a correlacionar de verdad en vez
        de asumir que los tres canales dicen siempre lo mismo."""
        for inc in self.incidentes_bus:
            if inc["incidente_id"] in self._incidentes_vistos:
                continue
            self._incidentes_vistos.add(inc["incidente_id"])
            if random.random() < P_REPORTAR_EN_CHAT:
                return inc
            self.stats["incidentes_bus_no_reportados"] += 1
        return None

    async def _poll_bus(self):
        """El bus es la fuente de verdad de qué incidentes están pasando. Si no
        está levantado, el chat sigue funcionando solo con charla local."""
        while True:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    res = await client.get(f"{BUS_URL}/api/incidentes/activos")
                    res.raise_for_status()
                    self.incidentes_bus = res.json()["incidentes"]
                    self.bus_conectado = True
            except Exception:
                self.bus_conectado = False
            await asyncio.sleep(5)

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
            asyncio.create_task(self._poll_bus())

    def set_speed(self, mode: str):
        if mode in SPEED_PRESETS:
            self.speed_mode = mode


engine = ChatEngine()
app = FastAPI()


@app.on_event("startup")
async def on_startup():
    engine.start()
    print(f"[devchat] token requerido para /api/* y /ws -> {API_TOKEN}", flush=True)
    print(f"[devchat] bus de incidentes -> {BUS_URL}", flush=True)


@app.get("/")
async def index():
    html = (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")
    html = html.replace("__API_TOKEN__", API_TOKEN)
    return HTMLResponse(html)


@app.get("/api/channels")
async def get_channels(_: None = Depends(require_token)):
    return {"channels": CHANNELS}


@app.get("/api/history")
async def get_history(limit: int = 50, channel: str | None = None, _: None = Depends(require_token)):
    items = engine.history
    if channel:
        items = [m for m in items if m["canal"] == channel]
    return {"messages": items[-limit:]}


@app.post("/api/speed")
async def set_speed(payload: dict, _: None = Depends(require_token)):
    engine.set_speed(payload.get("mode", "normal"))
    return {"speed_mode": engine.speed_mode}


@app.get("/api/stats")
async def get_stats():
    """Groundtruth de monitoreo — no linkeado desde la UI del chat. Cuenta
    la realidad (mensajes/hilos, incidente vs normal) para medir después
    contra lo que detecte el agente."""
    return {**engine.stats, "bus_conectado": engine.bus_conectado}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if websocket.query_params.get("token") != API_TOKEN:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    engine.connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        engine.connections.discard(websocket)


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
