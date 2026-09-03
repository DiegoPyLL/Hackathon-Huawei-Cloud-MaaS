#!/usr/bin/env python3
"""Ejecuta el flujo multiagente sobre el dataset JSONL de monitoreo."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.maas_demo.config import Config, ConfigError  # noqa: E402
from src.maas_demo.dotenv import load_dotenv  # noqa: E402
from src.maas_demo.orchestrator import Orchestrator  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta una corrida por línea JSONL.")
    parser.add_argument("--mode", choices=("mock", "live"))
    parser.add_argument("--input", type=Path, default=ROOT / "projects/monitoreo/data/monitoreo_dumps.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evals/results/corrida.jsonl")
    args = parser.parse_args()
    try:
        load_dotenv(ROOT / ".env")
        if args.mode:
            os.environ["MAAS_MODE"] = args.mode
        config = Config.from_env()
        orchestrator = Orchestrator(config)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.input.open(encoding="utf-8") as source, args.output.open("w", encoding="utf-8") as destination:
            for number, raw in enumerate(source, 1):
                if not raw.strip():
                    continue
                try:
                    record = json.loads(raw)
                    if not isinstance(record, dict):
                        raise ValueError("la línea debe ser un objeto JSON")
                    events = list(orchestrator.stream(record))
                    result = orchestrator.store.get(events[-1]["run_id"]) if events else None
                    if result is None:
                        raise ValueError("la corrida no produjo resultado")
                    destination.write(json.dumps(result, ensure_ascii=False) + "\n")
                    print(f"[OK] línea {number} · {result['run_id']} · {result['status']}")
                except Exception as error:
                    failure = {"line": number, "mode": config.mode, "status": "fallida", "error": str(error)}
                    destination.write(json.dumps(failure, ensure_ascii=False) + "\n")
                    print(f"[FALLÓ] línea {number} · {error}", file=sys.stderr)
        return 0
    except (ConfigError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
