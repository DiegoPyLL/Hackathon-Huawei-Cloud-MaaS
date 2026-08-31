"""Caso de uso de conversación independiente del proveedor."""

from __future__ import annotations

import time
from collections.abc import Iterator, Sequence
from typing import Any

from .provider import ChatProvider, Event, Message


SYSTEM_PROMPT = """Eres un copiloto para convertir retos ambiguos en planes demostrables.
Responde en español claro. Prioriza una acción, evidencia medible y riesgos reales.
No afirmes que se usó un servicio cloud: la interfaz muestra el modo de ejecución.
"""
MAX_MESSAGES = 20
MAX_CONTENT_LENGTH = 4_000


class ValidationError(ValueError):
    """La petición del cliente incumple el contrato público."""


class ChatService:
    def __init__(self, provider: ChatProvider) -> None:
        self.provider = provider

    def stream(self, messages: Any) -> Iterator[Event]:
        validated = self._validate(messages)
        with_system = [{"role": "system", "content": SYSTEM_PROMPT}, *validated]
        return self._timed_stream(with_system)

    def complete(self, messages: Any) -> dict[str, Any]:
        content = []
        metadata: dict[str, Any] = {}
        for event in self.stream(messages):
            if event["type"] == "delta":
                content.append(event["delta"])
            elif event["type"] == "done":
                metadata = event
        return {"content": "".join(content), **metadata}

    def _timed_stream(self, messages: Sequence[Message]) -> Iterator[Event]:
        started = time.perf_counter()
        for event in self.provider.stream(messages):
            if event["type"] == "done":
                event = {**event, "latency_ms": round((time.perf_counter() - started) * 1000)}
            yield event

    @staticmethod
    def _validate(messages: Any) -> list[Message]:
        if not isinstance(messages, list) or not messages:
            raise ValidationError("messages debe ser una lista no vacía.")
        if len(messages) > MAX_MESSAGES:
            raise ValidationError(f"La conversación admite como máximo {MAX_MESSAGES} mensajes.")

        validated = []
        for index, message in enumerate(messages):
            if not isinstance(message, dict):
                raise ValidationError(f"messages[{index}] debe ser un objeto.")
            role = message.get("role")
            content = message.get("content")
            if role not in {"user", "assistant"}:
                raise ValidationError(f"messages[{index}].role no es válido.")
            if not isinstance(content, str) or not content.strip():
                raise ValidationError(f"messages[{index}].content no puede estar vacío.")
            if len(content) > MAX_CONTENT_LENGTH:
                raise ValidationError(
                    f"messages[{index}].content supera {MAX_CONTENT_LENGTH} caracteres."
                )
            validated.append({"role": role, "content": content.strip()})
        if validated[-1]["role"] != "user":
            raise ValidationError("El último mensaje debe pertenecer al usuario.")
        return validated
