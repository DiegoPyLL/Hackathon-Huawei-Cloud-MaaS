"""Orquestación del análisis: del Pull Request a la decisión."""

from __future__ import annotations

from typing import Any

from . import agent, cost, github, policy, publish
from .budget import Budget
from .context import build_analysis_context


MAX_FILE_CHARS = 8_000


def merge_findings(
    rule_findings: list[dict[str, Any]], llm_findings: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Une ambas fuentes. Ante el mismo (tipo, archivo) gana la regla determinista."""
    merged = list(rule_findings)
    seen = {(item["type"], item.get("file")) for item in rule_findings}

    for item in llm_findings:
        key = (item["type"], item.get("file"))
        if key not in seen:
            seen.add(key)
            merged.append(item)

    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    merged.sort(key=lambda item: order.get(item["severity"], 9))
    return merged


def _relevant_files(
    payload: dict[str, Any], report: dict[str, Any]
) -> list[dict[str, Any]]:
    """Archivos que superan el umbral de importancia, con su patch."""
    selected = {item["filename"] for item in report["llm_analysis_queue"]}
    return [item for item in payload["files"] if item["filename"] in selected]


def _file_reader(payload: dict[str, Any], token: str | None):
    """Permite leer solo archivos que el Pull Request toca."""
    allowed = {item["filename"] for item in payload["files"]}
    repository = payload["repository"]
    ref = payload["pull_request"].get("head_sha")

    def read(name: str) -> str:
        if name not in allowed:
            raise github.PullRequestError(f"'{name}' no forma parte del Pull Request.")
        return github.get_file_content(
            repository, name, ref, token=token, max_chars=MAX_FILE_CHARS
        )

    return read


def analyze_payload(
    payload: dict[str, Any],
    *,
    provider: Any,
    mode: str,
    environment: str = policy.DEFAULT_ENVIRONMENT,
    token: str | None = None,
    budget: Budget | None = None,
) -> dict[str, Any]:
    """Analiza un Pull Request ya descargado y emite la decisión."""
    # Se valida antes de razonar: un entorno inválido no debe costar una llamada.
    policy.environment_settings(environment)

    budget = budget or Budget()
    prepared = build_analysis_context(payload)

    reasoning = agent.analyze(
        prepared["context"],
        provider=provider,
        budget=budget,
        read_file=_file_reader(payload, token),
    )

    # Las reglas se aplican solo a los archivos que el ranking considera
    # relevantes: la documentación con ejemplos no debe generar hallazgos.
    relevant = _relevant_files(payload, prepared["report"])

    estimate = cost.estimate_cost(relevant)
    rule_findings = policy.evaluate(relevant, environment)
    rule_findings += policy.cost_finding(estimate, environment)

    findings = merge_findings(rule_findings, reasoning["findings"])
    score = policy.risk_score(findings)
    decision = policy.decide(score, findings)

    return {
        "repository": payload["repository"],
        "pull_request": payload["pull_request"],
        "environment": environment,
        "mode": mode,
        "decision": decision,
        "risk_score": score,
        "findings": findings,
        "cost": estimate,
        "suggested_action": "GENERATE_PATCH" if decision == "BLOCK" else "REVIEW",
        "ranking": prepared["report"]["files_by_importance"],
        "savings": prepared["savings"],
        "budget": budget.report(),
        "notes": reasoning["notes"],
    }


def analyze_pull_request(
    repository: str,
    pr_number: int,
    *,
    provider: Any,
    mode: str,
    environment: str = policy.DEFAULT_ENVIRONMENT,
    token: str | None = None,
    publish_result: bool = True,
) -> dict[str, Any]:
    """Descarga el Pull Request, lo analiza y publica el veredicto."""
    payload = github.build_payload(repository, pr_number, token=token)
    report = analyze_payload(
        payload,
        provider=provider,
        mode=mode,
        environment=environment,
        token=token,
    )

    if publish_result:
        # Un fallo al publicar no invalida el análisis: se informa y se sigue.
        report["publication"] = publish.publish(report, pr_number, token)

    return report
