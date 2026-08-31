#!/usr/bin/env python3
"""Prueba una instancia desplegada y permite exigir que use Huawei MaaS en vivo."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prueba HTTP de humo del vertical slice.")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--require-mode", choices=("mock", "live"))
    return parser.parse_args()


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)


def stream_once(base_url: str) -> dict:
    request = urllib.request.Request(
        f"{base_url}/api/chat/stream",
        data=json.dumps(
            {"messages": [{"role": "user", "content": "Resume el valor de esta demo."}]}
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    done = None
    received_content = False
    with urllib.request.urlopen(request, timeout=90) as response:
        for raw_line in response:
            line = raw_line.decode().strip()
            if not line.startswith("data:"):
                continue
            event = json.loads(line.removeprefix("data:").strip())
            if event.get("type") == "error":
                raise RuntimeError(event["error"])
            if event.get("type") == "delta" and event.get("delta"):
                received_content = True
            if event.get("type") == "done":
                done = event
    if not received_content or done is None:
        raise RuntimeError("El stream no entregó contenido y evento final.")
    return done


def main() -> int:
    args = parse_args()
    base_url = args.url.rstrip("/")
    try:
        health = fetch_json(f"{base_url}/api/health")
        done = stream_once(base_url)
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as error:
        print(f"FALLÓ: {error}", file=sys.stderr)
        return 1

    if args.require_mode and done.get("mode") != args.require_mode:
        print(
            f"FALLÓ: se exigió modo {args.require_mode}, respondió {done.get('mode')}.",
            file=sys.stderr,
        )
        return 1
    print(
        f"APROBADO: estado={health['status']} modo={done['mode']} "
        f"modelo={done['model']} latencia={done['latency_ms']} ms"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
