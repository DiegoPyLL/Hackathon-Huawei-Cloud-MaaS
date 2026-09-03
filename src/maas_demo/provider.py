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
        system_prompt = next(
            (message["content"] for message in messages if message["role"] == "system"),
            "",
        )
        subject = " ".join(prompt.split())[:120]
        role_source = system_prompt or prompt
        role = next((line.strip() for line in role_source.splitlines() if line.strip().startswith("ROL:")), "")
        if role == "ROL: triage":
            answer = _mock_triage(prompt)
        elif role in {"ROL: dba", "ROL: sysadmin", "ROL: secops"}:
            answer = _mock_finding(prompt, role.removeprefix("ROL: ").strip())
        elif role == "ROL: consolidador":
            answer = _mock_report(prompt)
        else:
            answer = ""
        if answer:
            for chunk in _chunks(answer):
                yield {"type": "delta", "delta": chunk}
            yield {"type": "done", "mode": "mock", "model": self.model, "request_id": "mock-deterministic"}
            return
        answer = (
            "Tipo de incidente\n"
            "Clasificación pendiente de confirmar contra los 8 tipos canónicos "
            "(indisponibilidad, degradación, error funcional, acceso e "
            "identidad, datos, integración y terceros, capacidad, seguridad).\n\n"
            "Causa raíz probable\n"
            f"Incidente reportado: {subject}.\n"
            "El patrón dominante en los logs adjuntos apunta a un único origen; "
            "revisa la línea con mayor frecuencia de error y el ID de alerta que "
            "la acompaña antes de confirmar.\n\n"
            "Evidencia\n"
            "Cita la línea de log exacta, el timestamp y el ID de alerta que "
            "respaldan la causa raíz — sin esos tres datos la conclusión no es "
            "defendible.\n\n"
            "Qué se descartó\n"
            "Nombra cada hipótesis alternativa considerada y el dato puntual que "
            "la descartó, para dejar el razonamiento visible.\n\n"
            "Acción correctiva\n"
            "Propone una corrección concreta y reversible; no afirmes haberla "
            "ejecutado, solo describe el plan y cómo verificarlo."
        )
        for chunk in _chunks(answer):
            yield {"type": "delta", "delta": chunk}
        yield {
            "type": "done",
            "mode": "mock",
            "model": self.model,
            "request_id": "mock-deterministic",
        }


def _mock_triage(prompt: str) -> str:
    """Deterministic triage for local orchestration tests; it never reads groundtruth."""
    text = prompt.lower()
    incidents: list[dict[str, Any]] = []
    def add(title: str, tipo: str, specialists: list[str], evidence: list[str], severity: str = "alta", attack: bool = False) -> None:
        incidents.append({"id": f"INC-{len(incidents)+1:02d}", "titulo": title, "tipo": tipo,
            "canal": "monitoreo", "severidad": severity, "ataque_activo": attack,
            "evidencia": evidence[:5], "especialistas": specialists[:2],
            "motivo_ruteo": "Ruteo determinado por la señal dominante y la tabla canónica."})
    if "401" in text and ("varios usuarios" in text or text.count("user=") >= 3):
        add("Ráfaga de accesos fallidos", "acceso-identidad", ["secops"], ["Patrón 401 contra múltiples identidades"], attack=True)
    if "lock_wait" in text or "transaccion" in text and "bloque" in text:
        add("Bloqueo del motor de datos", "datos", ["dba"], ["Señal de bloqueo o espera del motor"])
    if "cpu.pct" in text or "mem.available" in text or "conn.active" in text:
        add("Saturación de capacidad", "capacidad", ["sysadmin"], ["Métrica de capacidad por encima del límite"])
    if "503" in text and ("trafico" in text or "req/min" in text):
        add("Caída por agotamiento de conexiones", "indisponibilidad", ["sysadmin", "secops"], ["Respuestas 503 y tráfico anómalo"])
    if "timeout" in text and ("proveedor" in text or "pasarela" in text or "upstream" in text):
        add("Fallo de proveedor externo", "integracion-terceros", ["sysadmin"], ["Timeout concentrado en dependencia externa"])
    if "169.254.169.254" in text or "credencial" in text and "repositorio" in text:
        add("Actividad de seguridad sospechosa", "seguridad", ["secops"], ["Señal de acceso a metadata o credencial expuesta"], "critica")
    if not incidents:
        add("Incidente de monitoreo", "degradacion", ["sysadmin"], ["El volcado requiere investigación adicional"], "media")
    return json.dumps({"version": "1", "incidentes": incidents, "descartados": []}, ensure_ascii=False)


def _mock_finding(prompt: str, specialist: str) -> str:
    match = next((line for line in prompt.splitlines() if line.startswith("INCIDENTE_JSON:")), "")
    incident = json.loads(match.removeprefix("INCIDENTE_JSON:") or "{}")
    return json.dumps({"version": "1", "incidente_id": incident.get("id", "INC-01"),
        "especialista": specialist, "causa_raiz": "La evidencia disponible requiere confirmación operativa.",
        "confianza": "media", "evidencia": incident.get("evidencia", [])[:2], "descartado": [],
        "viabilidad": "requiere_mas_datos", "accion": None}, ensure_ascii=False)


def _mock_report(prompt: str) -> str:
    return ("Tipo de incidente\nIncidentes clasificados por el Orquestador.\n\n"
            "Causa raíz probable\nLos especialistas entregaron hallazgos con evidencia acotada.\n\n"
            "Evidencia\nSe citan las evidencias incluidas en los hallazgos.\n\n"
            "Qué se descartó\nLas señales no incidentales aparecen explícitamente en el triage.\n\n"
            "Acción correctiva\nLas acciones propuestas quedan sujetas a la compuerta de aprobación humana.")


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


def build_provider(config: Any, model: str | None = None) -> ChatProvider:
    if config.mode == "mock":
        return MockProvider(model=model or config.model)
    return MaaSProvider(
        api_key=config.api_key,
        base_url=config.base_url,
        model=model or config.model,
        timeout_seconds=config.timeout_seconds,
    )
