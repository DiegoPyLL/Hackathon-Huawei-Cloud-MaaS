"""Publicación del veredicto en el Pull Request: comentario y etiqueta.

El comentario se actualiza en su sitio en lugar de acumular uno por ejecución,
y solo una etiqueta de veredicto queda aplicada a la vez.
"""

from __future__ import annotations

from typing import Any

from .github import (
    DEFAULT_API_URL,
    GitHubHTTPError,
    PullRequestError,
    github_request,
    parse_repo,
)


# Marca invisible que permite reconocer el comentario del agente.
MARKER = "<!-- ai-cloud-deployment-guardian -->"

LABELS = {
    "APPROVE": {
        "name": "guardian:approve",
        "color": "0e8a16",
        "description": "AI Cloud Deployment Guardian: sin riesgos relevantes",
    },
    "WARN": {
        "name": "guardian:warn",
        "color": "fbca04",
        "description": "AI Cloud Deployment Guardian: riesgos no críticos",
    },
    "BLOCK": {
        "name": "guardian:block",
        "color": "b60205",
        "description": "AI Cloud Deployment Guardian: despliegue bloqueado",
    },
}

VERDICT_HEADLINE = {
    "APPROVE": "APROBADO",
    "WARN": "REVISIÓN NECESARIA",
    "BLOCK": "DESPLIEGUE BLOQUEADO",
}

SEVERITY_ICON = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "⚪"}


def render_comment(report: dict[str, Any]) -> str:
    """Redacta el comentario.

    Nunca reproduce el valor de un secreto: solo el archivo donde aparece.
    """
    decision = report["decision"]
    lines = [
        MARKER,
        "## AI Cloud Deployment Guardian",
        "",
        f"**{VERDICT_HEADLINE[decision]}** · Risk Score **{report['risk_score']}/100** "
        f"· entorno `{report['environment']}` · ejecución `{report['mode']}`",
        "",
    ]

    findings = report["findings"]
    if findings:
        lines += ["| | Severidad | Tipo | Archivo | Detalle |", "|---|---|---|---|---|"]
        for item in findings:
            icon = SEVERITY_ICON.get(item["severity"], "")
            archivo = f"`{item['file']}`" if item.get("file") else "—"
            policy = f" ({item['policy']})" if item.get("policy") else ""
            lines.append(
                f"| {icon} | {item['severity']} | `{item['type']}` | {archivo} | "
                f"{item['message']}{policy} |"
            )
    else:
        lines.append("No se detectaron riesgos en los archivos relevantes.")

    cost = report.get("cost") or {}
    if cost.get("applicable"):
        lines += [
            "",
            f"**Coste estimado:** {cost['previous_cost']} → {cost['estimated_cost']} "
            f"unidades relativas ({cost['increase_percent']:+}%).",
        ]

    savings = report["savings"]
    budget = report["budget"]
    lines += [
        "",
        "<details><summary>Presupuesto de la ejecución</summary>",
        "",
        f"- Archivos analizados: {savings['files_selected']} de {savings['files_total']}",
        f"- Tokens enviados: {savings['context_tokens']} "
        f"(el diff completo son {savings['full_diff_tokens']})",
        f"- Llamadas al modelo: {budget['llm_calls']} · "
        f"lecturas de archivo: {budget['tool_calls']}",
        "",
        "</details>",
    ]

    if decision == "BLOCK":
        lines += ["", "Hay una corrección disponible en `POST /api/guardian/patch`."]

    return "\n".join(lines)


def _issue_url(api_url: str, repository: str, pr_number: int) -> str:
    owner, repo = parse_repo(repository)
    return f"{api_url.rstrip('/')}/repos/{owner}/{repo}/issues/{pr_number}"


def find_comment(issue_url: str, token: str) -> int | None:
    """Busca el comentario previo del agente por su marca."""
    page = 1
    while True:
        comments = github_request(f"{issue_url}/comments?per_page=100&page={page}", token)
        if not comments:
            return None
        for comment in comments:
            if MARKER in (comment.get("body") or ""):
                return comment["id"]
        if len(comments) < 100:
            return None
        page += 1


def upsert_comment(
    api_url: str, repository: str, pr_number: int, body: str, token: str
) -> dict[str, Any]:
    """Crea el comentario o actualiza el que ya existe."""
    issue_url = _issue_url(api_url, repository, pr_number)
    existing = find_comment(issue_url, token)

    if existing is None:
        created = github_request(f"{issue_url}/comments", token, method="POST", data={"body": body})
        return {"action": "created", "url": created["html_url"]}

    owner, repo = parse_repo(repository)
    updated = github_request(
        f"{api_url.rstrip('/')}/repos/{owner}/{repo}/issues/comments/{existing}",
        token,
        method="PATCH",
        data={"body": body},
    )
    return {"action": "updated", "url": updated["html_url"]}


def ensure_label(api_url: str, repository: str, label: dict[str, str], token: str) -> None:
    """Crea la etiqueta si no existe. Que ya exista no es un error."""
    owner, repo = parse_repo(repository)
    try:
        github_request(
            f"{api_url.rstrip('/')}/repos/{owner}/{repo}/labels",
            token,
            method="POST",
            data=label,
        )
    except GitHubHTTPError as error:
        if error.status != 422:  # 422 = ya existe
            raise


def sync_label(
    api_url: str, repository: str, pr_number: int, decision: str, token: str
) -> str:
    """Deja aplicada solo la etiqueta del veredicto actual."""
    label = LABELS[decision]
    issue_url = _issue_url(api_url, repository, pr_number)
    current = [item["name"] for item in github_request(issue_url, token).get("labels") or []]

    for name in current:
        if name.startswith("guardian:") and name != label["name"]:
            github_request(f"{issue_url}/labels/{name}", token, method="DELETE")

    if label["name"] not in current:
        ensure_label(api_url, repository, label, token)
        github_request(
            f"{issue_url}/labels", token, method="POST", data={"labels": [label["name"]]}
        )

    return label["name"]


def publish(
    report: dict[str, Any],
    pr_number: int,
    token: str | None,
    *,
    api_url: str = DEFAULT_API_URL,
) -> dict[str, Any]:
    """Publica veredicto y etiqueta. Un fallo aquí no invalida el análisis."""
    if not token:
        return {"published": False, "reason": "No hay GITHUB_TOKEN para escribir."}

    repository = report["repository"]

    try:
        comment = upsert_comment(
            api_url, repository, pr_number, render_comment(report), token
        )
        label = sync_label(api_url, repository, pr_number, report["decision"], token)
    except PullRequestError as error:
        return {"published": False, "reason": str(error)}

    return {
        "published": True,
        "comment": comment["url"],
        "comment_action": comment["action"],
        "label": label,
    }
