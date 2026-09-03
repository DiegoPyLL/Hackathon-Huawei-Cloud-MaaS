#!/usr/bin/env python3
"""Ejecuta el conjunto mínimo de casos contra mock o Huawei MaaS en vivo."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.maas_demo.config import Config, ConfigError  # noqa: E402
from src.maas_demo.dotenv import load_dotenv  # noqa: E402
from src.maas_demo.provider import ProviderError, build_provider  # noqa: E402
from src.maas_demo.service import ChatService  # noqa: E402


REQUIRED_HEADINGS = ("Causa raíz", "Evidencia", "Acción correctiva")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evalúa el vertical slice de MaaS.")
    parser.add_argument("--mode", choices=("mock", "live"))
    parser.add_argument("--cases", type=Path, default=PROJECT_ROOT / "evals" / "cases.json")
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_cases(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("El dataset debe ser una lista no vacía.")
    return payload


def evaluate_case(service: ChatService, case: dict[str, str]) -> dict[str, object]:
    try:
        result = service.complete([{"role": "user", "content": case["prompt"]}])
    except ProviderError as error:
        return {"id": case["id"], "segment": case["segment"], "passed": False, "error": str(error)}

    content = result["content"]
    checks = {
        "has_content": bool(content.strip()),
        "has_action": any(heading.lower() in content.lower() for heading in REQUIRED_HEADINGS),
        "mode_visible": result.get("mode") in {"mock", "live"},
        "latency_visible": isinstance(result.get("latency_ms"), int),
    }
    return {
        "id": case["id"],
        "segment": case["segment"],
        "passed": all(checks.values()),
        "checks": checks,
        "mode": result.get("mode"),
        "model": result.get("model"),
        "latency_ms": result.get("latency_ms"),
        "usage": result.get("usage"),
    }


def main() -> int:
    args = parse_args()
    try:
        if args.mode == "mock":
            os.environ["MAAS_MODE"] = "mock"
        else:
            load_dotenv(PROJECT_ROOT / ".env")
        if args.mode == "live":
            os.environ["MAAS_MODE"] = "live"
        config = Config.from_env()
        cases = load_cases(args.cases)
    except (ConfigError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    service = ChatService(build_provider(config))
    results = [evaluate_case(service, case) for case in cases]
    passed = sum(bool(result["passed"]) for result in results)
    latencies = [result["latency_ms"] for result in results if isinstance(result.get("latency_ms"), int)]
    report = {
        "mode": config.mode,
        "model": config.model,
        "passed": passed,
        "total": len(results),
        "pass_rate": passed / len(results),
        "latency_p50_ms": round(statistics.median(latencies)) if latencies else None,
        "results": results,
    }

    print(f"Evaluación {config.mode}/{config.model}: {passed}/{len(results)} casos")
    for result in results:
        mark = "APROBADO" if result["passed"] else "FALLÓ"
        detail = result.get("error") or f"{result.get('latency_ms')} ms"
        print(f"[{mark}] {result['id']} · {detail}")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Reporte: {args.json_out}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
