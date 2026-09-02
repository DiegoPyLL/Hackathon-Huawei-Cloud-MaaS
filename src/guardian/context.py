"""Construcción del contexto que llega al LLM: solo lo que el ranking aprueba."""

from __future__ import annotations

from typing import Any

from .budget import CHARS_PER_TOKEN, estimate_tokens
from .ranking import build_report


def selected_files(
    payload: dict[str, Any], report: dict[str, Any]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Empareja cada archivo de la cola del LLM con su patch, en orden de importancia."""
    patches = {item["filename"]: item for item in payload.get("files", [])}

    pairs = []
    for queued in report["llm_analysis_queue"]:
        source = patches.get(queued["filename"])
        if source and source.get("patch"):
            pairs.append((queued, source))
    return pairs


def build_llm_context(payload: dict[str, Any], report: dict[str, Any]) -> str:
    """Concatena únicamente los patches de los archivos relevantes.

    Deja fuera `score_breakdown` y `matched_directory_rule`: son para el
    panel humano y multiplicarían el prompt sin aportar razonamiento.
    """
    blocks = [
        f"--- {queued['filename']} "
        f"(importancia {queued['importance_index']}, {source['status']}) ---\n"
        f"{source['patch']}"
        for queued, source in selected_files(payload, report)
    ]
    return "\n\n".join(blocks)


def build_analysis_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Punto de entrada de la capa de datos: del PR crudo al contexto acotado."""
    report = build_report(payload)
    context = build_llm_context(payload, report)

    full_diff_chars = sum(len(item.get("patch") or "") for item in payload.get("files", []))

    return {
        "report": report,
        "context": context,
        "savings": {
            "files_total": len(payload.get("files", [])),
            "files_selected": len(report["llm_analysis_queue"]),
            "full_diff_tokens": round(full_diff_chars / CHARS_PER_TOKEN),
            "context_tokens": estimate_tokens(context),
        },
    }
