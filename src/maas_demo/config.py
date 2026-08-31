"""Configuración validada de la aplicación."""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_BASE_URL = "https://api-ap-southeast-1.modelarts-maas.com/v2"


class ConfigError(ValueError):
    """La configuración no permite arrancar de forma segura."""


@dataclass(frozen=True)
class Config:
    mode: str
    api_key: str | None
    base_url: str
    model: str
    timeout_seconds: float = 45.0

    @classmethod
    def from_env(cls) -> "Config":
        mode = os.getenv("MAAS_MODE", "mock").strip().lower()
        if mode not in {"mock", "live"}:
            raise ConfigError("MAAS_MODE debe ser 'mock' o 'live'.")

        api_key = os.getenv("MAAS_API_KEY", "").strip() or None
        if mode == "live" and api_key is None:
            raise ConfigError("MAAS_API_KEY es obligatoria cuando MAAS_MODE=live.")

        base_url = os.getenv("MAAS_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
        model = os.getenv("MAAS_MODEL", "glm-5.2").strip()
        if not base_url.startswith("https://"):
            raise ConfigError("MAAS_BASE_URL debe usar HTTPS.")
        if not model:
            raise ConfigError("MAAS_MODEL no puede estar vacío.")

        raw_timeout = os.getenv("MAAS_TIMEOUT_SECONDS", "45")
        try:
            timeout = float(raw_timeout)
        except ValueError as error:
            raise ConfigError("MAAS_TIMEOUT_SECONDS debe ser numérico.") from error
        if not 1 <= timeout <= 300:
            raise ConfigError("MAAS_TIMEOUT_SECONDS debe estar entre 1 y 300.")

        return cls(
            mode=mode,
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout,
        )
