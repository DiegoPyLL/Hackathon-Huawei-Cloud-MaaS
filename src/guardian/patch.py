"""Generación del parche seguro: segunda llamada al LLM, siempre bajo demanda."""

from __future__ import annotations

from typing import Any

from .agent import complete
from .budget import Budget


SYSTEM_PROMPT = """Eres un ingeniero de infraestructura cloud.
Recibes hallazgos de seguridad y los fragmentos de configuración que los causan.

Devuelve únicamente la configuración corregida, sin explicaciones y sin markdown.
Sustituye credenciales por referencias a un gestor de secretos, cierra los
rangos de red abiertos, ajusta el dimensionamiento y añade autoescalado
cuando falte. No cambies nada que no esté relacionado con un hallazgo.
"""


def build_prompt(findings: list[dict[str, Any]], files: list[dict[str, Any]]) -> str:
    """Incluye solo los patches de los archivos señalados por algún hallazgo."""
    affected = {item["file"] for item in findings if item.get("file")}
    patches = [
        f"--- {item['filename']} ---\n{item['patch']}"
        for item in files
        if item["filename"] in affected and item.get("patch")
    ]

    problems = "\n".join(
        f"- [{item['severity']}] {item['type']}: {item['message']}" for item in findings
    )

    return f"Hallazgos:\n{problems}\n\nConfiguración afectada:\n" + "\n\n".join(patches)


def generate(
    findings: list[dict[str, Any]],
    files: list[dict[str, Any]],
    *,
    provider: Any,
    mode: str,
    budget: Budget | None = None,
) -> dict[str, Any]:
    """Propone una configuración corregida para que la persona la revise."""
    budget = budget or Budget()

    if not findings:
        return {"mode": mode, "patch": None, "reason": "No hay hallazgos que corregir."}

    prompt = build_prompt(findings, files)
    budget.record_context(prompt)

    content = complete(
        provider,
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        budget,
    )

    return {"mode": mode, "patch": content.strip(), "budget": budget.report()}
