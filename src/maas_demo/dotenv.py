"""Carga mínima de variables conocidas desde .env, sin dependencias externas."""

from __future__ import annotations

import os
from pathlib import Path


ALLOWED_KEYS = {
    "MAAS_MODE",
    "MAAS_API_KEY",
    "MAAS_BASE_URL",
    "MAAS_MODEL",
    "MAAS_TIMEOUT_SECONDS",
}


def load_dotenv(path: Path) -> None:
    """Carga claves admitidas sin reemplazar variables ya exportadas."""
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in ALLOWED_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)
