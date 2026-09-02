"""Rule Engine determinista. Sus veredictos el LLM no los puede revertir."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .diff import added_lines


POLICIES_PATH = Path(__file__).parent / "policies" / "production.json"
DEFAULT_ENVIRONMENT = "production"


class PolicyError(ValueError):
    """La configuración de políticas no permite evaluar el cambio."""


@lru_cache(maxsize=1)
def load_policies() -> dict[str, Any]:
    return json.loads(POLICIES_PATH.read_text(encoding="utf-8"))


def environment_settings(environment: str) -> dict[str, Any]:
    environments = load_policies()["environments"]
    settings = environments.get(environment)
    if settings is None:
        raise PolicyError(
            f"Entorno '{environment}' desconocido. Disponibles: "
            f"{', '.join(sorted(environments))}."
        )
    return settings


def _finding(rule: dict[str, Any], filename: str, message: str | None = None) -> dict[str, Any]:
    return {
        "type": rule["type"],
        "severity": rule["severity"],
        "file": filename,
        "message": message or rule["message"],
        "policy": rule["id"],
        "source": "rule_engine",
    }


def _evaluate_rule(
    rule: dict[str, Any], filename: str, lines: list[str], settings: dict[str, Any]
) -> list[dict[str, Any]]:
    limit = settings.get(rule["setting"])

    if "numeric_pattern" in rule:
        pattern = re.compile(rule["numeric_pattern"], re.IGNORECASE)
        findings = []
        for line in lines:
            found = pattern.search(line)
            if found and int(found.group(1)) > limit:
                findings.append(
                    _finding(
                        rule,
                        filename,
                        f"{rule['message']} Declaradas {found.group(1)}, máximo {limit}.",
                    )
                )
        return findings[:1]

    # Booleanas: si el entorno lo permite, la regla no aplica.
    if limit is True:
        return []

    pattern = re.compile(rule["pattern"], re.IGNORECASE)
    ignore = re.compile(rule["ignore"], re.IGNORECASE) if "ignore" in rule else None

    for line in lines:
        if pattern.search(line) and not (ignore and ignore.search(line)):
            return [_finding(rule, filename)]
    return []


def evaluate(
    files: list[dict[str, Any]], environment: str = DEFAULT_ENVIRONMENT
) -> list[dict[str, Any]]:
    """Aplica las reglas no negociables a las líneas añadidas por el PR."""
    settings = environment_settings(environment)
    rules = load_policies()["rules"]

    findings = []
    for item in files:
        patch = item.get("patch") or ""
        if not patch:
            continue
        lines = added_lines(patch)
        filename = item.get("filename", "[desconocido]")
        for rule in rules:
            findings.extend(_evaluate_rule(rule, filename, lines, settings))

    return findings


def cost_finding(
    cost: dict[str, Any], environment: str = DEFAULT_ENVIRONMENT
) -> list[dict[str, Any]]:
    """Convierte un aumento de coste por encima de la política en un hallazgo."""
    if not cost.get("applicable"):
        return []

    limit = environment_settings(environment)["max_cost_increase_percent"]
    increase = cost["increase_percent"]

    if increase <= limit:
        return []

    return [
        {
            "type": "COST_INCREASE",
            "severity": "HIGH",
            "file": None,
            "message": (
                f"Aumento estimado de coste del {increase}%, "
                f"por encima del {limit}% permitido."
            ),
            "policy": "POLICY-COST-005",
            "source": "rule_engine",
        }
    ]


def risk_score(findings: list[dict[str, Any]]) -> int:
    """Suma la severidad de los hallazgos y satura en 100."""
    points = load_policies()["severity_points"]
    total = sum(points.get(item.get("severity", ""), 0) for item in findings)
    return min(100, total)


def decide(score: int, findings: list[dict[str, Any]]) -> str:
    """Decide el despliegue.

    Un hallazgo CRITICAL del Rule Engine bloquea siempre: una credencial
    filtrada no se compensa con la ausencia de otros problemas.
    """
    if any(
        item["severity"] == "CRITICAL" and item["source"] == "rule_engine"
        for item in findings
    ):
        return "BLOCK"

    bands = load_policies()["decision_bands"]
    if score >= bands["BLOCK"]:
        return "BLOCK"
    if score >= bands["WARN"]:
        return "WARN"
    return "APPROVE"
