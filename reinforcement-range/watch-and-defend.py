#!/usr/bin/env python3
"""Mira los logs de acceso del contenedor objetivo en vivo y se los pasa
al Incident Response Agent (el analista original, solo lectura) para que
diagnostique el ataque mientras está ocurriendo. No ejecuta nada — es el
mismo ChatService de solo texto, aplicado a tráfico real en vez de casos
de prueba.
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.maas_demo.config import Config  # noqa: E402
from src.maas_demo.dotenv import load_dotenv  # noqa: E402
from src.maas_demo.provider import ProviderError, build_provider  # noqa: E402
from src.maas_demo.service import ChatService  # noqa: E402

CONTAINER = "rr-target"
POLL_SECONDS = 20


def fetch_new_logs(since: str) -> tuple[str, str]:
    now = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(
        ["docker", "logs", "--since", since, "--until", now, CONTAINER],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return (result.stdout + result.stderr).strip(), now


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    config = Config.from_env()
    service = ChatService(build_provider(config))
    print(f"Vigilando {CONTAINER} cada {POLL_SECONDS}s — modo {config.mode}/{config.model}")
    print("Ctrl+C para detener.\n")

    since = datetime.now(timezone.utc).isoformat()
    try:
        while True:
            time.sleep(POLL_SECONDS)
            chunk, since = fetch_new_logs(since)
            if not chunk:
                continue
            print(f"--- {len(chunk.splitlines())} líneas nuevas, consultando al analista ---")
            prompt = (
                "Canal: sistema de monitoreo (logs de acceso en vivo de un servicio "
                f"web bajo posible ataque activo). Log crudo:\n{chunk}"
            )
            try:
                result = service.complete([{"role": "user", "content": prompt}])
            except ProviderError as error:
                print(f"[error del proveedor: {error}]")
                continue
            print(result["content"])
            print(f"[modo={result.get('mode')} latencia={result.get('latency_ms')}ms]\n")
    except KeyboardInterrupt:
        print("\nDetenido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
