"""Bucle de razonamiento del agente con un protocolo JSON propio.

No depende de que el modelo soporte el campo `tools` de la API: el contrato
son dos objetos JSON, lo que permite ejercitar el bucle con cualquier
proveedor, incluido el determinista de la demo.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from .budget import Budget


SYSTEM_PROMPT = """Eres un revisor de cambios de infraestructura cloud.
Analizas el diff de un Pull Request y detectas riesgos de seguridad,
configuración y sobreaprovisionamiento.

Responde SIEMPRE con un único objeto JSON, sin texto alrededor y sin markdown.
Solo dos formas son válidas:

{"action": "need_files", "files": ["ruta/archivo"], "reason": "por qué"}
{"action": "findings", "findings": [{"type": "...", "severity": "LOW|MEDIUM|HIGH|CRITICAL", "file": "...", "message": "..."}]}

Pide archivos solo si el diff es realmente insuficiente. Cada petición
consume presupuesto. Si no encuentras riesgos, devuelve findings vacío.
"""

SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict[str, Any] | None:
    """Rescata el objeto JSON de una respuesta que puede traer ruido alrededor."""
    found = JSON_OBJECT.search(text)
    if not found:
        return None
    try:
        payload = json.loads(found.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def normalize_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Se queda solo con hallazgos bien formados; descarta el resto en silencio."""
    raw = payload.get("findings")
    if not isinstance(raw, list):
        return []

    findings = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity", "")).upper()
        message = item.get("message")
        if severity not in SEVERITIES or not isinstance(message, str) or not message:
            continue
        findings.append(
            {
                "type": str(item.get("type") or "LLM_FINDING").upper(),
                "severity": severity,
                "file": item.get("file"),
                "message": message,
                "policy": None,
                "source": "llm",
            }
        )
    return findings


def complete(provider: Any, messages: list[dict[str, str]], budget: Budget) -> str:
    """Consume el stream del proveedor hasta obtener la respuesta completa."""
    content: list[str] = []
    for event in provider.stream(messages):
        if event["type"] == "delta":
            content.append(event["delta"])
        elif event["type"] == "done":
            budget.record_llm_call(event)
    return "".join(content)


def analyze(
    context: str,
    *,
    provider: Any,
    budget: Budget,
    read_file: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Ejecuta el bucle observar-razonar-pedir-decidir dentro del presupuesto.

    Devuelve los hallazgos del modelo. Las reglas deterministas se aplican
    fuera, y prevalecen sobre lo que diga el modelo.
    """
    budget.record_context(context)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Diff del Pull Request:\n\n{context}"},
    ]

    notes: list[str] = []

    while True:
        answer = complete(provider, messages, budget)
        payload = extract_json(answer)

        if payload is None:
            notes.append("El modelo no devolvió JSON válido; se usan solo las reglas.")
            return {"findings": [], "notes": notes}

        if payload.get("action") != "need_files":
            return {"findings": normalize_findings(payload), "notes": notes}

        if read_file is None or budget.exhausted():
            notes.append("Presupuesto agotado: se fuerza la decisión con lo disponible.")
            messages.append({"role": "assistant", "content": answer})
            messages.append(
                {
                    "role": "user",
                    "content": "Sin presupuesto para más archivos. Responde ya con action=findings.",
                }
            )
            final = extract_json(complete(provider, messages, budget))
            return {
                "findings": normalize_findings(final) if final else [],
                "notes": notes,
            }

        served = _serve_files(payload.get("files"), read_file, budget, notes)
        messages.append({"role": "assistant", "content": answer})
        messages.append({"role": "user", "content": served})


def _serve_files(
    requested: Any,
    read_file: Callable[[str], str],
    budget: Budget,
    notes: list[str],
) -> str:
    """Entrega los archivos pedidos, sin repetir ninguno ya servido."""
    if not isinstance(requested, list):
        return "Petición inválida. Responde con action=findings."

    blocks = []
    for name in requested:
        if not isinstance(name, str):
            continue
        if name in budget.served_files:
            notes.append(f"Relectura rechazada: {name}")
            blocks.append(f"--- {name} ---\n[YA ENTREGADO ANTES]")
            continue
        if not budget.can_serve(name):
            notes.append(f"Presupuesto insuficiente para: {name}")
            blocks.append(f"--- {name} ---\n[NO DISPONIBLE: presupuesto agotado]")
            continue
        try:
            content = read_file(name)
        except Exception as error:  # el fallo de una tool no debe abortar el análisis
            notes.append(f"No se pudo leer {name}: {error}")
            blocks.append(f"--- {name} ---\n[NO DISPONIBLE]")
            continue
        budget.record_served(name, content)
        blocks.append(f"--- {name} ---\n{content}")

    return "\n\n".join(blocks) or "No hay archivos adicionales disponibles."
