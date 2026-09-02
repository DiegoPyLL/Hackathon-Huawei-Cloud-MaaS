#!/usr/bin/env python3
"""
read_pr_diff.py

Obtiene el diff de un Pull Request de GitHub y lo prepara para
AI Cloud Deployment Guardian.

Requisitos:
    pip install requests

Autenticación:
    export GITHUB_TOKEN="github_pat_..."

Uso:
    python read_pr_diff.py --repo owner/repository --pr 42
    python read_pr_diff.py --repo owner/repository --pr 42 --json
    python read_pr_diff.py --repo owner/repository --pr 42 --output pr_42_diff.json

También soporta GitHub Enterprise:
    python read_pr_diff.py \
        --repo owner/repository \
        --pr 42 \
        --api-url https://github.example.com/api/v3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests


DEFAULT_API_URL = "https://api.github.com"
DEFAULT_MAX_CHARS = 60_000
REQUEST_TIMEOUT = 30


class PullRequestDiffError(RuntimeError):
    """Error al consultar o procesar un Pull Request."""


def parse_repo(repo: str) -> tuple[str, str]:
    """Valida y separa owner/repository."""
    parts = repo.strip().strip("/").split("/")

    if len(parts) != 2 or not all(parts):
        raise PullRequestDiffError(
            "El repositorio debe tener formato: owner/repository"
        )

    return parts[0], parts[1]


def build_headers(token: str | None, accept: str) -> dict[str, str]:
    """Construye headers para GitHub API."""
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AI-Cloud-Deployment-Guardian",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def github_get(
    url: str,
    token: str | None,
    accept: str = "application/vnd.github+json",
) -> requests.Response:
    """Ejecuta un GET contra GitHub API."""
    try:
        response = requests.get(
            url,
            headers=build_headers(token, accept),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise PullRequestDiffError(
            f"No se pudo conectar con GitHub: {exc}"
        ) from exc

    if response.status_code == 401:
        raise PullRequestDiffError(
            "GitHub rechazó la autenticación. Verifica GITHUB_TOKEN."
        )

    if response.status_code == 403:
        raise PullRequestDiffError(
            "Acceso denegado por GitHub o límite de API alcanzado."
        )

    if response.status_code == 404:
        raise PullRequestDiffError(
            "Pull Request o repositorio no encontrado."
        )

    if not response.ok:
        raise PullRequestDiffError(
            f"GitHub API respondió {response.status_code}: "
            f"{response.text[:500]}"
        )

    return response


def get_pull_request(
    api_url: str,
    owner: str,
    repo: str,
    pr_number: int,
    token: str | None,
) -> dict[str, Any]:
    """Obtiene metadata del Pull Request."""
    url = f"{api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    response = github_get(url, token)

    try:
        return response.json()
    except ValueError as exc:
        raise PullRequestDiffError(
            "GitHub devolvió metadata inválida."
        ) from exc


def get_pull_request_diff(
    api_url: str,
    owner: str,
    repo: str,
    pr_number: int,
    token: str | None,
) -> str:
    """Obtiene el diff completo del Pull Request."""
    url = f"{api_url}/repos/{owner}/{repo}/pulls/{pr_number}"

    response = github_get(
        url,
        token,
        accept="application/vnd.github.v3.diff",
    )

    return response.text.strip()


def get_changed_files(
    api_url: str,
    owner: str,
    repo: str,
    pr_number: int,
    token: str | None,
) -> list[dict[str, Any]]:
    """Obtiene los archivos modificados usando paginación."""
    files: list[dict[str, Any]] = []
    page = 1

    while True:
        url = (
            f"{api_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"
            f"?per_page=100&page={page}"
        )

        response = github_get(url, token)
        batch = response.json()

        if not isinstance(batch, list):
            raise PullRequestDiffError(
                "Respuesta inesperada al obtener archivos modificados."
            )

        files.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    return files


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    """Limita el tamaño del diff para controlar consumo de tokens."""
    if len(text) <= max_chars:
        return text, False

    suffix = (
        "\n\n[DIFF TRUNCADO: se alcanzó el límite de "
        f"{max_chars} caracteres]"
    )

    return text[:max_chars] + suffix, True


def build_payload(
    api_url: str,
    repository: str,
    pr_number: int,
    token: str | None,
    max_chars: int,
) -> dict[str, Any]:
    """Construye el payload que consumirá el agente LLM."""
    owner, repo = parse_repo(repository)

    pr = get_pull_request(
        api_url,
        owner,
        repo,
        pr_number,
        token,
    )

    files = get_changed_files(
        api_url,
        owner,
        repo,
        pr_number,
        token,
    )

    diff = get_pull_request_diff(
        api_url,
        owner,
        repo,
        pr_number,
        token,
    )

    diff, truncated = truncate_text(diff, max_chars)

    changed_files = [
        {
            "filename": item.get("filename"),
            "status": item.get("status"),
            "additions": item.get("additions", 0),
            "deletions": item.get("deletions", 0),
            "changes": item.get("changes", 0),
        }
        for item in files
    ]

    return {
        "repository": f"{owner}/{repo}",
        "pull_request": {
            "number": pr_number,
            "title": pr.get("title"),
            "state": pr.get("state"),
            "draft": pr.get("draft", False),
            "author": (pr.get("user") or {}).get("login"),
            "base_branch": (pr.get("base") or {}).get("ref"),
            "head_branch": (pr.get("head") or {}).get("ref"),
            "base_sha": (pr.get("base") or {}).get("sha"),
            "head_sha": (pr.get("head") or {}).get("sha"),
            "html_url": pr.get("html_url"),
        },
        "summary": {
            "changed_files": len(changed_files),
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),
            "commits": pr.get("commits", 0),
        },
        "files": changed_files,
        "diff": diff,
        "diff_truncated": truncated,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Lee el diff de un Pull Request de GitHub para "
            "AI Cloud Deployment Guardian."
        )
    )

    parser.add_argument(
        "--repo",
        required=True,
        help="Repositorio en formato owner/repository.",
    )

    parser.add_argument(
        "--pr",
        required=True,
        type=int,
        help="Número del Pull Request.",
    )

    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"URL base de GitHub API. Default: {DEFAULT_API_URL}",
    )

    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=(
            "Máximo de caracteres del diff incluidos en el payload. "
            f"Default: {DEFAULT_MAX_CHARS}"
        ),
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime todo el payload JSON.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Guarda el payload JSON en un archivo.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    token = os.getenv("GITHUB_TOKEN")

    try:
        payload = build_payload(
            api_url=args.api_url.rstrip("/"),
            repository=args.repo,
            pr_number=args.pr,
            token=token,
            max_chars=args.max_chars,
        )
    except PullRequestDiffError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    if args.json:
        print(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        pr = payload["pull_request"]
        summary = payload["summary"]

        print(
            f"PR #{pr['number']}: {pr['title']}\n"
            f"Repositorio: {payload['repository']}\n"
            f"Branch: {pr['head_branch']} -> {pr['base_branch']}\n"
            f"Archivos modificados: {summary['changed_files']}\n"
            f"Additions: +{summary['additions']}\n"
            f"Deletions: -{summary['deletions']}\n"
            f"\n{'=' * 80}\n"
            f"{payload['diff']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
