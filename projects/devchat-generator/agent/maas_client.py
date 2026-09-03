"""
Cliente para Huawei Cloud MaaS (vía Kostra), API compatible con OpenAI.

Model routing:
  - Modelo barato (deepseek-v4-flash) para clasificar/deduplicar.
  - Modelo fuerte (qwen3-32b) para resumen ejecutivo y recomendación final.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)


def _extract_json(content: str) -> dict:
    """Extrae JSON de la respuesta del modelo, manejando code blocks de markdown."""
    if not content:
        raise ValueError("respuesta vacía del modelo")
    m = _CODE_BLOCK_RE.search(content)
    if m:
        content = m.group(1).strip()
    return json.loads(content)


@dataclass
class MaaSConfig:
    api_key: str
    base_url: str
    model_cheap: str = "glm-5.2"
    model_strong: str = "glm-5.2"
    timeout: float = 45.0

    @classmethod
    def from_env(cls) -> "MaaSConfig":
        default_model = os.environ.get("MAAS_MODEL", "glm-5.2")
        return cls(
            api_key=os.environ.get("MAAS_API_KEY", ""),
            base_url=os.environ.get("MAAS_BASE_URL", "https://ai.kostra.cloud/v1"),
            model_cheap=os.environ.get("MAAS_MODEL_CHEAP", default_model),
            model_strong=os.environ.get("MAAS_MODEL_STRONG", default_model),
            timeout=float(os.environ.get("MAAS_TIMEOUT_SECONDS", "45")),
        )


class MaaSClient:
    def __init__(self, config: MaaSConfig | None = None):
        self.config = config or MaaSConfig.from_env()
        self._client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        response_format: dict | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": model or self.config.model_cheap,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        if response_format:
            kwargs["response_format"] = response_format
        return self._client.chat.completions.create(**kwargs)

    def chat_json(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> dict:
        resp = self.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        return _extract_json(content)

    def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.1,
    ) -> Any:
        return self.chat(
            messages=messages,
            model=model,
            tools=tools,
            temperature=temperature,
        )
