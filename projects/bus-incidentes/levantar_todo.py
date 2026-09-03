#!/usr/bin/env python3
"""
Levanta todos los sistemas interconectados con un solo comando.

    python levantar_todo.py

Arranca, en este orden (el bus primero porque los demas leen de el):

    bus         :8010   fuente de verdad de los incidentes
    dev-chat    :8000   chat tipo Slack, comenta los incidentes del bus
    semaforo    :8028   dashboard + logs, se pone rojo con los del bus

Ctrl+C corta los tres.
"""

import signal
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

SERVICIOS = [
    ("bus", BASE_DIR, "bus:app", 8010),
    ("dev-chat", PROJECTS / "devchat-generator" / "channels" / "devchat" / "live_simulator", "server:app", 8000),
    ("semaforo", PROJECTS / "Metricas(polling)", "main:app", 8028),
]


def main():
    procesos = []
    try:
        for nombre, cwd, app, puerto in SERVICIOS:
            print(f"[levantar] {nombre:9s} -> http://localhost:{puerto}")
            procesos.append(subprocess.Popen(
                [str(VENV_PY), "-m", "uvicorn", app, "--port", str(puerto)],
                cwd=str(cwd),
            ))
            # El bus tiene que estar arriba antes de que los otros lo consulten.
            time.sleep(2)

        print("\n  Semaforo y logs : http://localhost:8028")
        print("  Dev chat        : http://localhost:8000")
        print("  Bus (API)       : http://localhost:8010/api/verdad")
        print("\nCtrl+C para cortar todo.\n")

        signal.pause() if hasattr(signal, "pause") else _esperar(procesos)
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


def _esperar(procesos):
    """Windows no tiene signal.pause()."""
    while True:
        time.sleep(1)
        if any(p.poll() is not None for p in procesos):
            print("[levantar] un servicio murio, cortando el resto")
            return


if __name__ == "__main__":
    main()
