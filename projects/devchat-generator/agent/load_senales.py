"""
Cargador de señales desde los tres canales (dev chat, email, monitoring).

Convierte los JSONL generados al formato unificado SenalEntrante.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .schema import Canal, SenalEntrante


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def load_devchat(path: str | Path) -> list[SenalEntrante]:
    raw = _load_jsonl(Path(path))
    senales = []
    for item in raw:
        mensajes = item.get("mensajes", [])
        texto = " | ".join(f"@{m['autor']}: {m['texto']}" for m in mensajes)
        senales.append(SenalEntrante(
            canal=Canal.devchat,
            id_externo=item["thread_id"],
            timestamp=datetime.fromisoformat(item["timestamp_inicio"]),
            servicio_afectado=item.get("servicio_afectado"),
            texto=texto,
            metadata={
                "canal_chat": item.get("canal"),
                "n_mensajes": len(mensajes),
            },
        ))
    return senales


def load_email(path: str | Path) -> list[SenalEntrante]:
    raw = _load_jsonl(Path(path))
    senales = []
    for item in raw:
        texto = f"Subject: {item['subject']}\n\n{item['body']}"
        senales.append(SenalEntrante(
            canal=Canal.email,
            id_externo=item["ticket_id"],
            timestamp=datetime.fromisoformat(item["timestamp"]),
            servicio_afectado=item.get("servicio_afectado"),
            texto=texto,
            metadata={
                "remitente": item.get("remitente"),
                "prioridad_declarada": item.get("prioridad_declarada"),
                "tipo_remitente": item.get("tipo_remitente"),
            },
        ))
    return senales


def load_monitoring(path: str | Path) -> list[SenalEntrante]:
    raw = _load_jsonl(Path(path))
    senales = []
    for item in raw:
        metric = item.get("metric", {})
        texto = (
            f"Alert: {item.get('alert_name', 'unknown')} on "
            f"{item.get('servicio_afectado', 'unknown')} "
            f"({item.get('environment', 'unknown')})\n"
            f"State: {item.get('alert_state', 'unknown')}\n"
            f"Metric: {metric.get('name', '')}={metric.get('value', '')} "
            f"(threshold {metric.get('threshold', '')})\n"
            f"Description: {item.get('annotations', {}).get('description', '')}"
        )
        senales.append(SenalEntrante(
            canal=Canal.monitoring,
            id_externo=item["alert_id"],
            timestamp=datetime.fromisoformat(item["timestamp"]),
            servicio_afectado=item.get("servicio_afectado"),
            texto=texto,
            metadata={
                "alert_name": item.get("alert_name"),
                "alert_state": item.get("alert_state"),
                "environment": item.get("environment"),
                "metric_name": metric.get("name"),
                "metric_value": metric.get("value"),
                "metric_threshold": metric.get("threshold"),
            },
        ))
    return senales


def load_all(base_dir: str | Path) -> list[SenalEntrante]:
    base = Path(base_dir)
    senales: list[SenalEntrante] = []
    senales.extend(load_devchat(base / "channels" / "devchat" / "data" / "dev_chat_tickets.jsonl"))
    senales.extend(load_email(base / "channels" / "email" / "data" / "email_tickets.jsonl"))
    senales.extend(load_monitoring(base / "channels" / "monitoring" / "data" / "monitoring_alerts.jsonl"))
    senales.sort(key=lambda s: s.timestamp)
    return senales
