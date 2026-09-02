"""Índice de importancia: decide qué archivos merecen tokens del LLM."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any


RULES_PATH = Path(__file__).parent / "policies" / "importance.json"


@lru_cache(maxsize=1)
def load_rules() -> dict[str, Any]:
    """Carga las tablas de puntuación externalizadas."""
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def repo_path(filename: str) -> PurePosixPath:
    return PurePosixPath(filename.replace("\\", "/"))


def file_type_score(filename: str, rules: dict[str, Any]) -> tuple[int, str]:
    path = repo_path(filename)
    basename = path.name.lower()

    special = rules["special_file"].get(basename)
    if special is not None:
        return special, basename

    if basename.startswith(".env."):
        return rules["env_prefix_score"], ".env.*"

    suffix = path.suffix.lower()
    default = rules["defaults"]["extension"]
    return rules["extension"].get(suffix, default), suffix or "[sin extensión]"


def directory_score(filename: str, rules: dict[str, Any]) -> tuple[int, str]:
    """Puntúa por ubicación: gana la carpeta más sensible de la ruta completa."""
    dirs = [part.lower() for part in repo_path(filename).parts[:-1]]

    if not dirs:
        return rules["defaults"]["root_directory"], "[root]"

    best_score = rules["defaults"]["directory"]
    best_rule = dirs[-1]

    for directory in dirs:
        for keyword, score in rules["directory"].items():
            if keyword in directory and score > best_score:
                best_score = score
                best_rule = directory

    return best_score, best_rule


def change_size_score(file_data: dict[str, Any]) -> int:
    changes = file_data.get("changes")

    if not isinstance(changes, int):
        changes = int(file_data.get("additions", 0) or 0) + int(
            file_data.get("deletions", 0) or 0
        )

    if changes <= 0:
        return 5

    # Escala logarítmica para que un archivo enorme no eclipse a un
    # archivo pequeño pero crítico, por ejemplo .env.
    return max(5, min(100, round(15 + 42.5 * math.log10(changes))))


def priority(score: float, rules: dict[str, Any]) -> str:
    for name, floor in rules["priority_bands"].items():
        if score >= floor:
            return name
    return "MINIMAL"


def rank_file(file_data: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    filename = file_data.get("filename")
    if not filename:
        raise ValueError("Elemento de files sin 'filename'.")

    type_score, detected_format = file_type_score(filename, rules)
    dir_score, matched_directory = directory_score(filename, rules)
    size_score = change_size_score(file_data)
    status_score = rules["status"].get(
        str(file_data.get("status", "")).lower(), rules["defaults"]["status"]
    )

    weights = rules["weights"]
    score = (
        type_score * weights["file_type"]
        + dir_score * weights["directory"]
        + size_score * weights["change_size"]
        + status_score * weights["status"]
    )
    score = round(max(0, min(100, score)), 2)

    folder = str(repo_path(filename).parent)

    return {
        "filename": filename,
        "folder": "[root]" if folder == "." else folder,
        "format": detected_format,
        "status": file_data.get("status"),
        "changes": file_data.get("changes", 0),
        "additions": file_data.get("additions", 0),
        "deletions": file_data.get("deletions", 0),
        "importance_index": score,
        "priority": priority(score, rules),
        "score_breakdown": {
            "file_type": type_score,
            "directory": dir_score,
            "change_size": size_score,
            "status": status_score,
        },
        "matched_directory_rule": matched_directory,
    }


def rank_folders(
    files: list[dict[str, Any]], rules: dict[str, Any]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for item in files:
        grouped[item["folder"]].append(item)

    threshold = rules["llm_queue_threshold"]
    folders = []

    for folder, items in grouped.items():
        scores = [item["importance_index"] for item in items]
        relevant = sum(score >= threshold for score in scores)
        diversity = min(100, relevant * 20)

        # Evita que una carpeta gane solo por contener muchos .md.
        score = round(
            max(scores) * 0.60 + (sum(scores) / len(scores)) * 0.30 + diversity * 0.10,
            2,
        )

        folders.append(
            {
                "folder": folder,
                "importance_index": score,
                "priority": priority(score, rules),
                "files_changed": len(items),
                "formats": sorted({item["format"] for item in items}),
                "top_file": max(items, key=lambda item: item["importance_index"])[
                    "filename"
                ],
            }
        )

    return sorted(folders, key=lambda item: item["importance_index"], reverse=True)


def build_report(payload: dict[str, Any]) -> dict[str, Any]:
    """Ordena los archivos del PR y marca cuáles llegarán al LLM."""
    files = payload.get("files")

    if not isinstance(files, list):
        raise ValueError("El JSON no contiene 'files'. Usa read_pr_diff.py --output.")

    rules = load_rules()
    threshold = rules["llm_queue_threshold"]

    ranked_files = [rank_file(item, rules) for item in files]
    ranked_files.sort(key=lambda item: item["importance_index"], reverse=True)

    return {
        "repository": payload.get("repository"),
        "pull_request": payload.get("pull_request"),
        "folders_by_importance": rank_folders(ranked_files, rules),
        "files_by_importance": ranked_files,
        "llm_analysis_queue": [
            {
                "filename": item["filename"],
                "importance_index": item["importance_index"],
                "priority": item["priority"],
            }
            for item in ranked_files
            if item["importance_index"] >= threshold
        ],
    }
