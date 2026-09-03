#!/usr/bin/env python3
"""
Levanta toda la demo con un solo comando.

    python levantar_todo.py            # todo en modo live
    python levantar_todo.py --mock     # sin gastar cuota de MaaS

Arranca en este orden, porque los de abajo leen de los de arriba:

    8010  bus         fuente de verdad de los incidentes
    8000  dev-chat    el equipo comenta los incidentes del bus
    8028  semaforo    dashboard de estado + consola de logs
    8001  demo        los 3 canales alimentando al agente en vivo
    8080  Agente 1    Incident Response Agent (analista, solo lectura)

Ctrl+C corta todo.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECTS = BASE_DIR.parent
REPO = PROJECTS.parent

VENV_PY = REPO / ".venv" / "Scripts" / "python.exe"
if not VENV_PY.exists():
    VENV_PY = REPO / ".venv" / "bin" / "python"
if not VENV_PY.exists():
    VENV_PY = Path(sys.executable)

DEVCHAT = PROJECTS / "devchat-generator" / "channels" / "devchat" / "live_simulator"

SERVICIOS = [
    ("bus", BASE_DIR, ["-m", "uvicorn", "bus:app", "--port", "8010"], 8010),
    ("dev-chat", DEVCHAT, ["-m", "uvicorn", "server:app", "--port", "8000"], 8000),
    ("semaforo", PROJECTS / "Metricas(polling)", ["-m", "uvicorn", "main:app", "--port", "8028"], 8028),
    ("demo", PROJECTS / "devchat-generator" / "demo", ["-m", "uvicorn", "live_server:app", "--port", "8001"], 8001),
    ("agente-1", REPO, ["-m", "src.maas_demo"], 8080),
]


def main():
    ap = argparse.ArgumentParser(description="Levanta la demo completa")
    ap.add_argument("--mock", action="store_true", help="sin llamadas reales a MaaS")
    args = ap.parse_args()

    entorno = dict(os.environ)
    entorno["MAAS_MODE"] = "mock" if args.mock else "live"

    procesos = []
    try:
        for nombre, cwd, cmd, puerto in SERVICIOS:
            print(f"[levantar] {nombre:9s} -> http://localhost:{puerto}")
            procesos.append(subprocess.Popen(
                [str(VENV_PY), *cmd], cwd=str(cwd), env=entorno,
            ))
            time.sleep(2)

        print(f"\n  modo MaaS: {entorno['MAAS_MODE']}\n")
        print("  Semaforo y logs   http://localhost:8028")
        print("  Dev chat          http://localhost:8000")
        print("  Demo del agente   http://localhost:8001")
        print("  Agente 1          http://localhost:8080")
        print("  Bus (API)         http://localhost:8010/api/verdad")
        print("\n  Provocar un incidente:")
        print('    curl -X POST http://localhost:8010/api/incidentes/provocar \\')
        print('      -H "Content-Type: application/json" -d \'{"escenario":"caida_tras_deploy"}\'')
        print("\n  Corrida del agente sobre los 3 canales:")
        print(f"    {VENV_PY.name} projects/agente-puente/puente.py")
        print("\nCtrl+C para cortar todo.\n")

        while True:
            time.sleep(1)
            if any(p.poll() is not None for p in procesos):
                print("[levantar] un servicio murio, cortando el resto")
                break
    except KeyboardInterrupt:
        pass
    finally:
        for p in procesos:
            p.terminate()
        for p in procesos:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("\n[levantar] todo detenido")


if __name__ == "__main__":
    main()
