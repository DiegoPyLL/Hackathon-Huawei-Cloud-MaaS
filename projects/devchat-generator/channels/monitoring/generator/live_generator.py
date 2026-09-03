#!/usr/bin/env python3
"""
Generador de monitoring en vivo.

Produce alertas en tiempo real (firing + resolved) y las emite via callback.
Las alertas firing son incidentes; las resolved son ruido (alerta que se
recuperó sola). Pensado para correr dentro del demo server unificado.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime

from .generate_monitoring_alerts import CATEGORIES, SERVICES, ENVIRONMENTS, weighted_choice


class LiveMonitoringGenerator:
    def __init__(self, on_event):
        self.on_event = on_event
        self.speed_mode = "normal"
        self._task: asyncio.Task | None = None
        self._counter = 0
        self._firing: dict[str, dict] = {}

    SPEED_PRESETS = {
        "lento": (6.0, 12.0),
        "normal": (2.0, 6.0),
        "rapido": (0.5, 2.0),
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

        self._counter += 1
        alert_id = f"ALERT-LIVE-{self._counter:04d}"

        labels = {
            "service": servicio,
            "environment": env,
            "severity": severidad if es_incidente else "info",
            "alertname": alert_name,
        }

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
            "labels": labels,
        }

        await self.on_event(event)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    def set_speed(self, mode: str):
        if mode in self.SPEED_PRESETS:
            self.speed_mode = mode
