"""Lectura de Pull Requests de GitHub conservando el patch de cada archivo."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_API_URL = "https://api.github.com"
DEFAULT_MAX_PATCH_CHARS = 12_000
REQUEST_TIMEOUT = 30
PER_PAGE = 100

ERRORS_BY_STATUS = {
    401: "GitHub rechazó la autenticación. Verifica GITHUB_TOKEN.",
    403: "Acceso denegado por GitHub o límite de API alcanzado.",
    404: "Pull Request o repositorio no encontrado.",
}


class PullRequestError(RuntimeError):
    """Error al consultar o procesar un Pull Request."""


class GitHubHTTPError(PullRequestError):
    """GitHub respondió con un código de error. Conserva el código."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


def parse_repo(repo: str) -> tuple[str, str]:
    """Valida y separa owner/repository."""
    parts = repo.strip().strip("/").split("/")

    if len(parts) != 2 or not all(parts):
        raise PullRequestError("El repositorio debe tener formato: owner/repository")

    return parts[0], parts[1]


def github_request(
    url: str,
    token: str | None,
    *,
    method: str = "GET",
    data: Any = None,
) -> Any:
    """Ejecuta una petición contra GitHub API y devuelve el JSON decodificado."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AI-Cloud-Deployment-Guardian",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        message = ERRORS_BY_STATUS.get(
            error.code, f"GitHub API respondió HTTP {error.code}."
        )
        raise GitHubHTTPError(message, error.code) from error
    except urllib.error.URLError as error:
        raise PullRequestError(f"No se pudo conectar con GitHub: {error.reason}") from error
    except (TimeoutError, json.JSONDecodeError) as error:
        raise PullRequestError("GitHub devolvió una respuesta inutilizable.") from error


def github_get(url: str, token: str | None) -> Any:
    """Ejecuta un GET contra GitHub API y devuelve el JSON decodificado."""
    return github_request(url, token)


def truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Limita el tamaño de un patch para controlar el consumo de tokens."""
    if len(text) <= max_chars:
        return text, False

    suffix = f"\n[PATCH TRUNCADO: límite de {max_chars} caracteres]"
    return text[:max_chars] + suffix, True


def get_pull_request(api_url: str, owner: str, repo: str, number: int, token: str | None):
    payload = github_get(f"{api_url}/repos/{owner}/{repo}/pulls/{number}", token)
    if not isinstance(payload, dict):
        raise PullRequestError("GitHub devolvió metadata inválida.")
    return payload


def get_changed_files(
    api_url: str, owner: str, repo: str, number: int, token: str | None
) -> list[dict[str, Any]]:
    """Obtiene los archivos modificados, con su patch, usando paginación."""
    files: list[dict[str, Any]] = []
    page = 1

    while True:
        url = (
            f"{api_url}/repos/{owner}/{repo}/pulls/{number}/files"
            f"?per_page={PER_PAGE}&page={page}"
        )
        batch = github_get(url, token)

        if not isinstance(batch, list):
            raise PullRequestError("Respuesta inesperada al obtener archivos modificados.")

        files.extend(batch)

        if len(batch) < PER_PAGE:
            return files

        page += 1


def build_payload(
    repository: str,
    pr_number: int,
    *,
    token: str | None = None,
    api_url: str = DEFAULT_API_URL,
    max_patch_chars: int = DEFAULT_MAX_PATCH_CHARS,
) -> dict[str, Any]:
    """Construye el payload que consumirán el ranking y el agente.

    El patch viaja dentro de cada archivo, no como un diff monolítico: es lo
    que permite enviar al LLM solo los archivos que el ranking selecciona.
    """
    owner, repo = parse_repo(repository)
    token = token if token is not None else os.getenv("GITHUB_TOKEN")
    api_url = api_url.rstrip("/")

    pull_request = get_pull_request(api_url, owner, repo, pr_number, token)
    raw_files = get_changed_files(api_url, owner, repo, pr_number, token)

    files = []
    for item in raw_files:
        # GitHub omite 'patch' en binarios y en archivos demasiado grandes.
        patch, truncated = truncate(item.get("patch") or "", max_patch_chars)
        files.append(
            {
                "filename": item.get("filename"),
                "status": item.get("status"),
                "additions": item.get("additions", 0),
                "deletions": item.get("deletions", 0),
                "changes": item.get("changes", 0),
                "patch": patch,
                "patch_truncated": truncated,
            }
        )

    return {
        "repository": f"{owner}/{repo}",
        "pull_request": {
            "number": pr_number,
            "title": pull_request.get("title"),
            "state": pull_request.get("state"),
            "draft": pull_request.get("draft", False),
            "author": (pull_request.get("user") or {}).get("login"),
            "base_branch": (pull_request.get("base") or {}).get("ref"),
            "head_branch": (pull_request.get("head") or {}).get("ref"),
            "base_sha": (pull_request.get("base") or {}).get("sha"),
            "head_sha": (pull_request.get("head") or {}).get("sha"),
            "html_url": pull_request.get("html_url"),
        },
        "summary": {
            "changed_files": len(files),
            "additions": pull_request.get("additions", 0),
            "deletions": pull_request.get("deletions", 0),
            "commits": pull_request.get("commits", 0),
        },
        "files": files,
    }


def get_file_content(
    repository: str,
    path: str,
    ref: str,
    *,
    token: str | None = None,
    api_url: str = DEFAULT_API_URL,
    max_chars: int = 8_000,
) -> str:
    """Lee un archivo completo del repositorio, para `read_changed_file`."""
    owner, repo = parse_repo(repository)
    token = token if token is not None else os.getenv("GITHUB_TOKEN")
    quoted = urllib.parse.quote(path)
    url = f"{api_url.rstrip('/')}/repos/{owner}/{repo}/contents/{quoted}?ref={ref}"

    payload = github_get(url, token)

    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        raise PullRequestError(f"No se pudo leer '{path}' como texto.")

    try:
        content = base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
    except (KeyError, ValueError) as error:
        raise PullRequestError(f"Contenido inválido para '{path}'.") from error

    return truncate(content, max_chars)[0]
