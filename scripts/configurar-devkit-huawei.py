#!/usr/bin/env python3
"""Configura HuaweiCloud DevKit para Codex, Claude Code y KooCLI.

El script no lee archivos .env ni recibe secretos por argumentos. La
autenticacion es interactiva y solo se inicia cuando se usa --auth.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


DEVKIT_VERSION = "1.0.2"
MIN_NODE_MAJOR = 22
MCP_START = "# BEGIN HUAWEICLOUD DEVKIT"
MCP_END = "# END HUAWEICLOUD DEVKIT"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODEX_CONFIG = PROJECT_ROOT / ".codex" / "config.toml"
CLAUDE_CONFIG = PROJECT_ROOT / ".mcp.json"
SUPPORTED_TARGETS = ("auto", "codex", "claude", "both")


def mcp_config_block() -> str:
    return f"""{MCP_START} (gestionado por scripts/configurar-devkit-huawei.py)
[mcp_servers.huaweicloud-devkit]
command = \"npx\"
args = [\"-y\", \"-p\", \"huaweicloud-devkit@{DEVKIT_VERSION}\", \"huaweicloud-devkit-mcp\"]
env_vars = [\"HW_ACCESS_KEY\", \"HW_SECRET_KEY\", \"HW_REGION\"]
startup_timeout_sec = 30
default_tools_approval_mode = \"writes\"
{MCP_END}
"""


def claude_mcp_config(*, native_windows: bool | None = None) -> dict[str, object]:
    """Configuracion MCP compartida, con referencias y nunca valores secretos."""
    if native_windows is None:
        native_windows = os.name == "nt"
    command = "cmd" if native_windows else "npx"
    command_args = ["/c", "npx"] if native_windows else []
    return {
        "type": "stdio",
        "command": command,
        "args": command_args
        + [
            "-y",
            "-p",
            f"huaweicloud-devkit@{DEVKIT_VERSION}",
            "huaweicloud-devkit-mcp",
        ],
        "env": {
            "HW_ACCESS_KEY": "${HW_ACCESS_KEY:-}",
            "HW_SECRET_KEY": "${HW_SECRET_KEY:-}",
            "HW_REGION": "${HW_REGION:-}",
        },
    }


class SetupError(RuntimeError):
    """Error esperado que puede corregir la persona que ejecuta el script."""


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise SetupError(f"No se encontro '{name}' en PATH.")
    return path


def command_output(command: Sequence[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SetupError(f"Fallo {' '.join(command)}: {detail or 'sin detalle'}")
    return result.stdout.strip()


def check_node() -> tuple[str, str]:
    node = executable("node")
    version = command_output([node, "--version"])
    match = re.fullmatch(r"v?(\d+)(?:\.\d+){0,2}", version)
    if match is None:
        raise SetupError(f"No se pudo interpretar la version de Node.js: {version}")
    if int(match.group(1)) < MIN_NODE_MAJOR:
        raise SetupError(
            f"HuaweiCloud DevKit requiere Node.js >= {MIN_NODE_MAJOR}; "
            f"se encontro {version}."
        )
    return node, version


def check_codex() -> tuple[str, str]:
    codex = executable("codex")
    version = command_output([codex, "--version"])
    return codex, version


def check_claude() -> tuple[str, str]:
    claude = executable("claude")
    version = command_output([claude, "--version"])
    return claude, version


def resolve_target(target: str) -> str:
    if target != "auto":
        return target

    has_codex = shutil.which("codex") is not None
    has_claude = shutil.which("claude") is not None
    if has_codex and has_claude:
        return "both"
    if has_codex:
        return "codex"
    if has_claude:
        return "claude"
    raise SetupError("No se encontro Codex ni Claude Code en PATH.")


def update_codex_config(*, dry_run: bool) -> bool:
    block = mcp_config_block()
    existing = CODEX_CONFIG.read_text(encoding="utf-8") if CODEX_CONFIG.exists() else ""

    if MCP_START in existing or MCP_END in existing:
        if MCP_START not in existing or MCP_END not in existing:
            raise SetupError(
                f"El bloque administrado esta incompleto en {CODEX_CONFIG}. "
                "Corrigelo antes de continuar."
            )
        pattern = re.compile(
            rf"{re.escape(MCP_START)}.*?{re.escape(MCP_END)}\n?",
            flags=re.DOTALL,
        )
        updated = pattern.sub(block, existing, count=1)
    elif "[mcp_servers.huaweicloud-devkit]" in existing:
        raise SetupError(
            f"Ya existe una configuracion no administrada para HuaweiCloud en {CODEX_CONFIG}."
        )
    else:
        separator = "" if not existing or existing.endswith("\n\n") else "\n"
        updated = f"{existing}{separator}{block}"

    if updated == existing:
        return False
    if not dry_run:
        CODEX_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CODEX_CONFIG.write_text(updated, encoding="utf-8", newline="\n")
    return True


def is_huaweicloud_devkit_config(value: object) -> bool:
    """Distingue nuestra entrada de otra configuracion con el mismo nombre."""
    if not isinstance(value, dict):
        return False
    args = value.get("args")
    return (
        value.get("command") in ("npx", "cmd", "cmd.exe")
        and isinstance(args, list)
        and "huaweicloud-devkit-mcp" in args
        and any(
            isinstance(argument, str)
            and argument.startswith("huaweicloud-devkit@")
            for argument in args
        )
    )


def update_claude_config(*, dry_run: bool) -> bool:
    if CLAUDE_CONFIG.exists():
        try:
            document = json.loads(CLAUDE_CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise SetupError(
                f"No se pudo interpretar {CLAUDE_CONFIG}: {error.msg}."
            ) from error
    else:
        document = {}

    if not isinstance(document, dict):
        raise SetupError(f"La raiz de {CLAUDE_CONFIG} debe ser un objeto JSON.")

    servers = document.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise SetupError(f"'mcpServers' debe ser un objeto en {CLAUDE_CONFIG}.")

    desired = claude_mcp_config()
    existing = servers.get("huaweicloud-devkit")
    if existing is not None and existing != desired:
        if not is_huaweicloud_devkit_config(existing):
            raise SetupError(
                "Ya existe una configuracion no administrada para "
                f"HuaweiCloud en {CLAUDE_CONFIG}."
            )

    if existing == desired:
        return False

    servers["huaweicloud-devkit"] = desired
    if not dry_run:
        CLAUDE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CLAUDE_CONFIG.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return True


def print_config_state(path: Path, *, changed: bool, dry_run: bool) -> None:
    if dry_run and changed:
        state = "se actualizaria"
    else:
        state = "actualizada" if changed else "sin cambios"
    print(f"Configuracion MCP: {path} ({state})")


def run(command: Sequence[str], *, dry_run: bool) -> None:
    print(f"Ejecutando: {' '.join(command)}")
    if dry_run:
        return
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def npx_command(npx: str, *args: str) -> list[str]:
    if os.name == "nt":
        return ["cmd", "/c", npx, *args]
    return [npx, *args]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configura HuaweiCloud DevKit para Codex y/o Claude Code.",
    )
    parser.add_argument(
        "--target",
        choices=SUPPORTED_TARGETS,
        default="auto",
        help="Cliente MCP que se configura (predeterminado: auto).",
    )
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Inicia la configuracion interactiva de credenciales al finalizar.",
    )
    parser.add_argument(
        "--skip-koocli",
        action="store_true",
        help="No instala ni actualiza KooCLI.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra las acciones sin modificar archivos ni instalar componentes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        target = resolve_target(args.target)
        _, node_version = check_node()
        npx = executable("npx")
        clients: list[tuple[str, str]] = []

        print(f"Node.js: {node_version}")
        if target in ("codex", "both"):
            codex, codex_version = check_codex()
            clients.append(("Codex", codex))
            print(f"Codex: {codex_version}")

        if target in ("claude", "both"):
            claude, claude_version = check_claude()
            clients.append(("Claude Code", claude))
            print(f"Claude Code: {claude_version}")

        # Validar todos los ejecutables antes de modificar cualquiera de los archivos.
        if target in ("codex", "both"):
            changed = update_codex_config(dry_run=args.dry_run)
            print_config_state(CODEX_CONFIG, changed=changed, dry_run=args.dry_run)

        if target in ("claude", "both"):
            changed = update_claude_config(dry_run=args.dry_run)
            print_config_state(CLAUDE_CONFIG, changed=changed, dry_run=args.dry_run)

        package = f"huaweicloud-devkit@{DEVKIT_VERSION}"
        if not args.skip_koocli:
            run(
                npx_command(npx, "--yes", package, "install-hcloud"),
                dry_run=args.dry_run,
            )

        if args.auth:
            print("La autenticacion es interactiva. No pegues secretos en el repositorio.")
            run(
                npx_command(npx, "--yes", package, "auth", "init"),
                dry_run=args.dry_run,
            )

        for _, client in clients:
            run([client, "mcp", "list"], dry_run=args.dry_run)
    except SetupError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        if "node" in str(error).lower():
            print(
                "Instala Node.js 22 o superior en este mismo entorno "
                "y vuelve a ejecutar el script.",
                file=sys.stderr,
            )
        return 2
    except subprocess.CalledProcessError as error:
        print(
            f"ERROR: el comando termino con codigo {error.returncode}: {' '.join(error.cmd)}",
            file=sys.stderr,
        )
        return error.returncode or 1

    client_names = " y ".join(name for name, _ in clients)
    print(
        f"\nHuaweiCloud DevKit quedo configurado para {client_names}. "
        "Reinicia cada cliente y verifica con /mcp."
    )
    if not args.auth:
        print("Cuando quieras configurar credenciales, repite el comando con --auth.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
