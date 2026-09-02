#!/usr/bin/env python3
"""Descarga un Pull Request de GitHub para AI Cloud Deployment Guardian.

El patch viaja dentro de cada archivo, no como un diff monolítico: es lo que
permite que el ranking de importancia recorte de verdad el envío al modelo.

Autenticación (opcional en repositorios públicos):
    export GITHUB_TOKEN="github_pat_..."

Uso:
    python scripts/Caso1/scripts/read_pr_diff/read_pr_diff.py --repo owner/repo --pr 3 --output pr_3.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from guardian.github import (  # noqa: E402
    DEFAULT_MAX_PATCH_CHARS,
    PullRequestError,
    build_payload,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lee el diff de un Pull Request de GitHub.")
    parser.add_argument("--repo", required=True, help="Repositorio owner/repository.")
    parser.add_argument("--pr", required=True, type=int, help="Número del Pull Request.")
    parser.add_argument(
        "--max-patch-chars",
        type=int,
        default=DEFAULT_MAX_PATCH_CHARS,
        help=f"Máximo de caracteres por patch. Default: {DEFAULT_MAX_PATCH_CHARS}",
    )
    parser.add_argument("--json", action="store_true", help="Imprime el payload JSON.")
    parser.add_argument("--output", type=Path, help="Guarda el payload JSON en un archivo.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        payload = build_payload(args.repo, args.pr, max_patch_chars=args.max_patch_chars)
    except PullRequestError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.output:
        args.output.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    pr = payload["pull_request"]
    summary = payload["summary"]
    print(
        f"PR #{pr['number']}: {pr['title']}\n"
        f"Repositorio: {payload['repository']}\n"
        f"Branch: {pr['head_branch']} -> {pr['base_branch']}\n"
        f"Archivos modificados: {summary['changed_files']}\n"
        f"Additions: +{summary['additions']}  Deletions: -{summary['deletions']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
