#!/usr/bin/env python3
"""Deja que el modelo refuerce el contenedor objetivo con shell real,
via tool-calling, hasta el primer tope que se cumpla (configurable via
MAX_COMMANDS / TOTAL_BUDGET_MIN / PACE_SECONDS). Guarda todo en un
transcript que no se muestra hasta después de la fase de ataque, y
persiste la conversación en STATE_PATH para que la siguiente ronda
continúe donde quedó en vez de repetir reconocimiento.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

MAX_COMMANDS = int(os.environ.get("MAX_COMMANDS", "30"))
COMMAND_TIMEOUT_S = 30
TOTAL_BUDGET_S = int(os.environ.get("TOTAL_BUDGET_MIN", "30")) * 60
MAX_RETRIES = 5
PACE_SECONDS = float(os.environ.get("PACE_SECONDS", "12"))
CONTAINER = os.environ.get("TARGET_CONTAINER", "rr-target")

BASE_URL = os.environ.get("MAAS_BASE_URL", "https://ai.kostra.cloud/v1").rstrip("/")
API_KEY = os.environ["MAAS_API_KEY"]
MODEL = os.environ.get("MAAS_MODEL", "glm-5.2")

SYSTEM_PROMPT = f"""Eres un agente de hardening con acceso real a una shell dentro de un
contenedor aislado (sin salida a internet). Tu objetivo: encontrar y corregir
fallas de seguridad reales en la aplicación que corre ahí, usando el tool
run_shell para ejecutar comandos de verdad — no describas lo que harías, hazlo.

Reglas:
- Tienes como máximo {MAX_COMMANDS} acciones por sesión. Úsalas con criterio:
  prioriza reconocimiento rápido y luego arreglos concretos, no gastes turnos
  en exploración redundante — si ya investigaste algo en un mensaje anterior
  de esta misma conversación, no lo repitas. No vuelvas a leer un archivo que
  ya leíste antes en esta conversación; usa lo que ya sabes de su contenido.
- Cada comando corre dentro del contenedor objetivo, nunca fuera de él.
- No tienes acceso a internet ni falta que lo tengas.
- Secuencia obligatoria para que un arreglo tenga efecto real: primero EDITA
  el archivo fuente con el fix concreto (usa `sed -i`, o sobrescribe con un
  heredoc de `cat`/`python3` vía run_shell), y SOLO DESPUÉS de editar, llama
  al tool `restart_target` para que el proceso cargue el código nuevo.
- IMPORTANTE: `kill`/`os.kill()` contra el proceso principal (PID 1) desde
  run_shell NO FUNCIONA — el kernel de Linux protege a PID 1 de un namespace
  contra señales sin manejador, incluso SIGKILL, cuando la señal viene de
  adentro del mismo namespace (que es donde corre run_shell). Por eso existe
  el tool `restart_target`: reinicia desde fuera del namespace, donde sí
  tiene efecto. Nunca intentes matar o reiniciar el proceso con run_shell.
- Llamar a `restart_target` sin haber editado antes el código en esta misma
  sesión no arregla nada — el orquestador lo rechaza automáticamente.
- Cuando ya no quede nada más razonable por corregir con las acciones que te
  quedan, responde con texto plano (sin tool call) resumiendo qué hiciste y
  por qué, y termina ahí — no repitas acciones ya hechas.
- Nunca inventes que corriste un comando: si usas run_shell, es real y su
  resultado te llega como observación."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": (
                "Ejecuta un comando de shell real dentro del contenedor objetivo y "
                "devuelve stdout, stderr y código de salida. NOTA: matar o reiniciar "
                "el proceso principal (PID 1) desde aquí no funciona — el kernel "
                "protege a PID 1 de señales no manejadas quando vienen de dentro de "
                "su propio namespace. Usa el tool restart_target para reiniciar."
            ),
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restart_target",
            "description": (
                "Reinicia el proceso principal del contenedor objetivo desde fuera "
                "(vía el daemon de Docker en el host) para que tome el código que "
                "hayas editado. Solo tiene efecto real si ya editaste el archivo "
                "fuente en un run_shell anterior — si no, vuelve a levantar el "
                "mismo bug."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


EDIT_PATTERNS = [
    re.compile(r"\bsed\s+-i\b"),
    re.compile(r">>?\s*/app/"),
    re.compile(r"\btee\s+/app/"),
    re.compile(r"open\([^)]*['\"]w"),
]
RESTART_PATTERNS = [
    re.compile(r"\bkill\s+(-\w+\s+)?1\b"),
    re.compile(r"os\.kill\(\s*1\s*,"),
    re.compile(r"\bkillall\b"),
]

_edited_since_restart = False


def gate_command(command: str) -> str | None:
    """Rechaza un reinicio/kill si no hubo una edición real del código antes
    en esta misma sesión. Estructural, no depende de que el modelo obedezca
    el prompt."""
    global _edited_since_restart
    if any(p.search(command) for p in EDIT_PATTERNS):
        _edited_since_restart = True
        return None
    if any(p.search(command) for p in RESTART_PATTERNS):
        if not _edited_since_restart:
            return (
                "AVISO del orquestador: kill/os.kill() contra PID 1 no tiene "
                "efecto desde aquí (protección del kernel de Linux para PID 1 "
                "de un namespace) y además no editaste el código fuente antes "
                "en esta sesión. Edita primero con run_shell, y usa el tool "
                "restart_target para reiniciar de verdad."
            )
        _edited_since_restart = False
    return None


def run_shell(command: str) -> dict:
    rejection = gate_command(command)
    if rejection:
        return {"stdout": "", "stderr": rejection, "exit_code": 1}
    try:
        result = subprocess.run(
            ["docker", "exec", CONTAINER, "sh", "-c", command],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_S,
        )
        return {
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-2000:],
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"comando cortado tras {COMMAND_TIMEOUT_S}s", "exit_code": -1}


def restart_container() -> dict:
    """Reinicia el contenedor desde el host (fuera de su namespace de PID),
    donde el kernel sí entrega la señal de apagado sin la inmunidad de PID 1."""
    result = subprocess.run(
        ["docker", "restart", "-t", "2", CONTAINER],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "exit_code": result.returncode,
    }


def call_model(messages: list[dict]) -> dict:
    payload = json.dumps(
        {
            "model": MODEL,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "reasoning_effort": "max",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code == 429 or error.code >= 500:
                wait = min(60, 2**attempt * 5)
                retry_after = error.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait = max(wait, float(retry_after))
                    except ValueError:
                        pass
                print(f"[HTTP {error.code} de Kostra, reintento {attempt + 1}/{MAX_RETRIES} en {wait:.0f}s]")
                time.sleep(wait)
                continue
            raise
    raise last_error  # type: ignore[misc]


def main() -> int:
    override = os.environ.get("TRANSCRIPT_PATH")
    if override:
        transcript_path = Path(override)
    else:
        transcript_dir = Path("reinforcement-range")
        existing = sorted(transcript_dir.glob("transcript-ronda*.json"))
        next_round = len(existing) + 1
        transcript_path = transcript_dir / f"transcript-ronda{next_round}.json"

    state_path = Path(os.environ.get("STATE_PATH", "reinforcement-range/state.json"))
    default_brief = (
        "Esta es la última ronda antes de que un equipo de pentesting "
        "ataque este sistema de verdad, en los próximos minutos. Revisa "
        "el estado actual (puede que ya hayas actuado antes) y usa las "
        "acciones que te quedan para reforzar lo que tenga más impacto "
        "real contra un atacante — prioriza por impacto, no por orden "
        "de descubrimiento."
    )
    brief = os.environ.get("HARDEN_BRIEF", default_brief)

    if state_path.exists():
        messages = json.loads(state_path.read_text(encoding="utf-8"))
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = SYSTEM_PROMPT
        messages.append({"role": "user", "content": brief})
        print(f"[continuando conversación previa: {len(messages)} mensajes cargados de {state_path}, system prompt actualizado]")
    else:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": brief},
        ]

    transcript: list[dict] = []
    started = time.time()

    def save_transcript() -> None:
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(
            json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        state_path.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        for turn in range(MAX_COMMANDS):
            if time.time() - started > TOTAL_BUDGET_S:
                print(f"[corte por tiempo total tras {turn} turnos]")
                break

            if turn > 0:
                time.sleep(PACE_SECONDS)
            completion = call_model(messages)
            choice = completion["choices"][0]
            message = choice["message"]
            messages.append(message)

            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                print(f"[el modelo terminó voluntariamente en el turno {turn}]")
                transcript.append({"turn": turn, "type": "final_text", "content": message.get("content")})
                break

            for call in tool_calls:
                global _edited_since_restart
                name = call["function"]["name"]
                args = json.loads(call["function"]["arguments"] or "{}")
                if name == "restart_target":
                    print(f"[{turn}] $ restart_target()")
                    if not _edited_since_restart:
                        observation = {
                            "stdout": "",
                            "stderr": (
                                "BLOQUEADO por el orquestador: no editaste el "
                                "código fuente en esta sesión antes de pedir el "
                                "reinicio. Edita primero con run_shell, luego "
                                "reinicia."
                            ),
                            "exit_code": 1,
                        }
                    else:
                        observation = restart_container()
                        _edited_since_restart = False
                else:
                    command = args["command"]
                    print(f"[{turn}] $ {command}")
                    observation = run_shell(command)
                transcript.append({"turn": turn, "tool": name, "args": args, "observation": observation})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(observation, ensure_ascii=False),
                    }
                )
        else:
            print(f"[corte por tope de {MAX_COMMANDS} comandos]")
    finally:
        save_transcript()
        print(f"Transcript guardado en {transcript_path} (no lo abras hasta después de atacar)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
