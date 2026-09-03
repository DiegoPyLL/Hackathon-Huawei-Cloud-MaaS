#!/usr/bin/env python3
"""
Generador de email en vivo.

Produce tickets de email en tiempo real (incidentes + solicitudes + ruido)
y los emite via callback. Pensado para correr dentro del demo server unificado.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime

from .generate_email_tickets import CATEGORIES, SERVICES, USERS, PRIORIDAD_POOL, weighted_choice


class LiveEmailGenerator:
    def __init__(self, on_event):
        self.on_event = on_event
        self.speed_mode = "normal"
        self._task: asyncio.Task | None = None
        self._counter = 0
        self._active_incidents: list[dict] = []

    SPEED_PRESETS = {
        "lento": (8.0, 16.0),
        "normal": (3.0, 8.0),
        "rapido": (1.0, 3.0),
    }

    async def run(self):
        while True:
            lo, hi = self.SPEED_PRESETS[self.speed_mode]
            await asyncio.sleep(random.uniform(lo, hi))
            await self._emit_one()

    async def _emit_one(self):
        categorias = list(CATEGORIES.keys())
        pesos = [CATEGORIES[c]["weight"] for c in categorias]
        category = random.choices(categorias, weights=pesos, k=1)[0]
        cfg = CATEGORIES[category]

        servicio = random.choice(SERVICES)
        remitente = random.choice(USERS)
        t0 = datetime.now()
        ctx = {"service": servicio, "hora": t0.strftime("%H:%M")}

        subject = random.choice(cfg["subjects"]).format(**ctx)
        body = random.choice(cfg["bodies"]).format(**ctx)

        severidad = weighted_choice(cfg["severidad_pool"]) if cfg["es_incidente"] else "n/a"
        prioridad = weighted_choice(PRIORIDAD_POOL)

        self._counter += 1
        ticket_id = f"EMAIL-LIVE-{self._counter:04d}"

        event = {
            "type": "email",
            "id": ticket_id,
            "timestamp": t0.isoformat(timespec="seconds"),
            "subject": subject,
            "body": body,
            "remitente": remitente[0],
            "tipo_remitente": remitente[1],
            "prioridad_declarada": prioridad,
            "servicio_afectado": servicio if cfg["es_incidente"] else None,
            "categoria_real": category,
            "es_incidente": cfg["es_incidente"],
            "severidad_real": severidad,
        }

        await self.on_event(event)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    def set_speed(self, mode: str):
        if mode in self.SPEED_PRESETS:
            self.speed_mode = mode
