"""Punto de entrada: python -m maas_demo."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .api import create_app
from .config import Config, ConfigError
from .dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Cloud Deployment Guardian.")
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

    print(f"AI Cloud Deployment Guardian: \033[36mhttp://{args.host}:{args.port}\033[0m")
    print(f"Modo: {config.mode} · Modelo: {config.model}")
    if config.mode == "mock":
        print("MOCK visible: no se realizarán llamadas a Huawei Cloud.")

    uvicorn.run(create_app(config), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
