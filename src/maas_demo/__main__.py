"""Punto de entrada: python -m src.maas_demo."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import Config, ConfigError
from .dotenv import load_dotenv
from .server import create_server


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Demo web de Huawei Cloud MaaS.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        load_dotenv(PROJECT_ROOT / ".env")
        config = Config.from_env()
    except (ConfigError, ValueError) as error:
        print(f"Error de configuración: {error}")
        return 2

    server = create_server(config, host=args.host, port=args.port)
    url = f"http://{args.host}:{server.server_port}"
    print(f"Huawei MaaS demo: \033[36m{url}\033[0m")
    print(f"Modo: {config.mode} · Modelo: {config.model}")
    if config.mode == "mock":
        print("MOCK visible: no se realizarán llamadas a Huawei Cloud.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
