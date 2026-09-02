#!/usr/bin/env python3
"""Ranking de importancia de los archivos de un Pull Request.

Decide qué archivos llegan al LLM y cuáles no cuestan un solo token.

Uso:
    python scripts/Caso1/scripts/read_pr_diff/read_pr_diff.py --repo owner/repo --pr 3 --output pr_3.json
    python scripts/Caso1/scripts/rank_importancia_archivo/rank_pr_importance.py pr_3.json --output pr_3_ranked.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from guardian.context import build_analysis_context  # noqa: E402


def print_report(report: dict, savings: dict) -> None:
    print("\nCARPETAS POR IMPORTANCIA")
    print("=" * 90)
    for item in report["folders_by_importance"]:
        print(
            f"{item['importance_index']:>6.2f}  {item['priority']:<10} "
            f"{item['files_changed']:>4} archivos  {item['folder']}"
        )

    print("\nARCHIVOS POR IMPORTANCIA")
    print("=" * 100)
    for item in report["files_by_importance"]:
        print(
            f"{item['importance_index']:>6.2f}  {item['priority']:<10} "
            f"{item['format']:<16} {item['changes']:>6}  {item['filename']}"
        )

    print("\nCOLA QUE LLEGA AL LLM")
    print("=" * 90)
    for index, item in enumerate(report["llm_analysis_queue"], 1):
        print(
            f"{index:>2}. [{item['priority']:<8}] "
            f"{item['importance_index']:>6.2f}  {item['filename']}"
        )

    print("\nPRESUPUESTO")
    print("=" * 90)
    print(
        f"Archivos: {savings['files_selected']} de {savings['files_total']}\n"
        f"Tokens del diff completo: {savings['full_diff_tokens']}\n"
        f"Tokens que se envían:     {savings['context_tokens']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ranking de importancia de un Pull Request.")
    parser.add_argument("input", type=Path, help="JSON generado con read_pr_diff.py --output.")
    parser.add_argument("--json", action="store_true", help="Imprime el resultado como JSON.")
    parser.add_argument("--output", type=Path, help="Guarda el ranking en JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        prepared = build_analysis_context(payload)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    report = {**prepared["report"], "savings": prepared["savings"]}

    if args.output:
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(prepared["report"], prepared["savings"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
