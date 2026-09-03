"""Configuración validada de la aplicación."""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_BASE_URL = "https://ai.kostra.cloud/v1"


class ConfigError(ValueError):
    """La configuración no permite arrancar de forma segura."""


@dataclass(frozen=True)
class Config:
    mode: str
    api_key: str | None
    base_url: str
    model: str
    timeout_seconds: float = 45.0
    modelo_triage: str | None = None
    modelo_especialista: str | None = None
    modelo_consolidacion: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        mode = os.getenv("MAAS_MODE", "mock").strip().lower()
        if mode not in {"mock", "live"}:
            raise ConfigError("MAAS_MODE debe ser 'mock' o 'live'.")

        api_key = os.getenv("MAAS_API_KEY", "").strip() or None
        if mode == "live" and api_key is None:
            raise ConfigError("MAAS_API_KEY es obligatoria cuando MAAS_MODE=live.")

        base_url = os.getenv("MAAS_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
        model = os.getenv("MAAS_MODEL", "deepseek-v4-pro").strip()
        if not base_url.startswith("https://"):
            raise ConfigError("MAAS_BASE_URL debe usar HTTPS.")
        if not model:
            raise ConfigError("MAAS_MODEL no puede estar vacío.")

        modelo_triage = os.getenv("MAAS_MODELO_TRIAGE", model).strip() or model
        modelo_especialista = os.getenv("MAAS_MODELO_ESPECIALISTA", model).strip() or model
        modelo_consolidacion = os.getenv("MAAS_MODELO_CONSOLIDACION", model).strip() or model
        supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/") or None
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or None
        if supabase_url and not supabase_url.startswith("https://"):
            raise ConfigError("SUPABASE_URL debe usar HTTPS.")

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
            modelo_triage=modelo_triage,
            modelo_especialista=modelo_especialista,
            modelo_consolidacion=modelo_consolidacion,
            supabase_url=supabase_url,
            supabase_service_role_key=supabase_key,
        )
