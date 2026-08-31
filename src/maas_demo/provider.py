"""Adaptadores de inferencia para Huawei MaaS y para una demo determinista."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Sequence
from typing import Any, Protocol


Message = dict[str, str]
Event = dict[str, Any]


class ProviderError(RuntimeError):
    """El proveedor no pudo completar la inferencia."""


class ChatProvider(Protocol):
    def stream(self, messages: Sequence[Message]) -> Iterator[Event]: ...


def _chunks(text: str, size: int = 44) -> Iterator[str]:
    for start in range(0, len(text), size):
        yield text[start : start + size]


class MockProvider:
    """Proveedor local explícito; nunca simula ser una llamada cloud real."""

    def __init__(self, model: str = "mock-brief-v1") -> None:
        self.model = model

    def stream(self, messages: Sequence[Message]) -> Iterator[Event]:
        prompt = next(
            (message["content"] for message in reversed(messages) if message["role"] == "user"),
            "",
        )
        subject = " ".join(prompt.split())[:120]
        answer = (
            "Resumen ejecutivo\n"
            f"El reto planteado es: {subject}.\n\n"
            "Acción prioritaria\n"
            "Construye primero un flujo extremo a extremo medible y elimina todo "
            "componente que no participe en la demostración.\n\n"
            "Evidencia para la demo\n"
            "Muestra el resultado, el modo de ejecución, la latencia y una prueba "
            "repetible que permita comparar la siguiente iteración."
        )
        for chunk in _chunks(answer):
            yield {"type": "delta", "delta": chunk}
        yield {
            "type": "done",
            "mode": "mock",
            "model": self.model,
            "request_id": "mock-deterministic",
        }


class MaaSProvider:
    """Cliente streaming para Huawei MaaS Standard API V2."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.opener = opener

    @property
    def chat_url(self) -> str:
        suffix = "/chat/completions"
        return self.base_url if self.base_url.endswith(suffix) else self.base_url + suffix

    def stream(self, messages: Sequence[Message]) -> Iterator[Event]:
        payload = json.dumps(
            {"model": self.model, "stream": True, "messages": list(messages)}
        ).encode("utf-8")
        request = urllib.request.Request(
            self.chat_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )

        received_content = False
        request_id = None
        usage = None
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line or line.startswith(":") or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError as error:
                        raise ProviderError("MaaS devolvió un evento SSE inválido.") from error

                    request_id = chunk.get("id", request_id)
                    usage = chunk.get("usage", usage)
                    choices = chunk.get("choices") or []
                    delta = choices[0].get("delta", {}) if choices else {}
                    content = delta.get("content")
                    if content:
                        received_content = True
                        yield {"type": "delta", "delta": content}
        except urllib.error.HTTPError as error:
            raise ProviderError(f"MaaS rechazó la solicitud con HTTP {error.code}.") from error
        except urllib.error.URLError as error:
            raise ProviderError("No se pudo conectar con Huawei MaaS.") from error
        except TimeoutError as error:
            raise ProviderError("Huawei MaaS superó el tiempo de espera.") from error

        if not received_content:
            raise ProviderError("Huawei MaaS terminó sin contenido utilizable.")
        yield {
            "type": "done",
            "mode": "live",
            "model": self.model,
            "request_id": request_id,
            "usage": usage,
        }


def build_provider(config: Any) -> ChatProvider:
    if config.mode == "mock":
        return MockProvider(model=config.model)
    return MaaSProvider(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
    )
