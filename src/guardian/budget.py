"""Presupuesto de tokens y de llamadas a herramientas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Aproximación suficiente para decidir recortes sin depender de un tokenizador.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estima tokens a partir de caracteres. Sirve para acotar, no para facturar."""
    return round(len(text) / CHARS_PER_TOKEN)


@dataclass
class Budget:
    """Acota el trabajo del agente y registra lo que realmente consumió."""

    max_tool_calls: int = 5
    max_context_tokens: int = 12_000

    tool_calls: int = 0
    context_tokens: int = 0
    llm_calls: int = 0
    served_files: set[str] = field(default_factory=set)
    usage: dict[str, Any] = field(default_factory=dict)

    def can_serve(self, filename: str) -> bool:
        """Un archivo ya servido nunca se vuelve a enviar: es la fuga más cara."""
        return (
            filename not in self.served_files
            and self.tool_calls < self.max_tool_calls
            and self.context_tokens < self.max_context_tokens
        )

    def record_context(self, text: str) -> None:
        self.context_tokens += estimate_tokens(text)

    def record_served(self, filename: str, text: str) -> None:
        self.served_files.add(filename)
        self.tool_calls += 1
        self.record_context(text)

    def record_llm_call(self, done_event: dict[str, Any]) -> None:
        """Acumula el `usage` que MaaS emite en su evento `done`."""
        self.llm_calls += 1
        reported = done_event.get("usage")
        if not isinstance(reported, dict):
            return
        for key, value in reported.items():
            if isinstance(value, int):
                self.usage[key] = self.usage.get(key, 0) + value

    def exhausted(self) -> bool:
        return (
            self.tool_calls >= self.max_tool_calls
            or self.context_tokens >= self.max_context_tokens
        )

    def report(self) -> dict[str, Any]:
        return {
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "estimated_context_tokens": self.context_tokens,
            "files_served": sorted(self.served_files),
            "reported_usage": self.usage or None,
        }
