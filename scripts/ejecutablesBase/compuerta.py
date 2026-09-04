#!/usr/bin/env python3
"""Compuerta de verificacion. Una tarea no esta hecha hasta que esto sale con 0.

Existe porque un agente que trabaja solo de madrugada tiene un incentivo
perverso: la forma mas barata de "hacer pasar los tests" es ablandarlos. Esta
compuerta lo impide con un trinquete: guarda el numero maximo de tests que
llego a ver y falla si el numero baja. Borrar un test para que la suite quede
verde deja de funcionar como atajo.

Comprueba, en orden de lo mas barato a lo mas caro:

  1. El arbol de git esta limpio (nada a medio hacer).
  2. Ningun .env quedo versionado.
  3. La suite pasa entera.
  4. El numero de tests no bajo respecto del maximo historico (trinquete).
  5. El flujo del agente corre de punta a punta en mock.

Uso:
    python scripts/ejecutablesBase/compuerta.py
    python scripts/ejecutablesBase/compuerta.py --rapida   # salta el paso 5
    python scripts/ejecutablesBase/compuerta.py --piso 159 # fija el trinquete a mano

Salida: 0 si todo pasa. 1 si algo falla, con el motivo en una linea.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVO_PISO = RAIZ / "noche" / ".piso-tests"


def _correr(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=RAIZ, capture_output=True, text=True,
        encoding="utf-8", errors="replace", **kwargs,
    )


def _python() -> str:
    """El interprete del venv si existe; si no, el que este corriendo esto."""
    for candidato in (RAIZ / ".venv" / "Scripts" / "python.exe", RAIZ / ".venv" / "bin" / "python"):
        if candidato.exists():
            return str(candidato)
    return sys.executable


class Fallo(Exception):
    """Una comprobacion no paso. El mensaje es lo que se le muestra al agente."""


def comprobar_arbol_limpio() -> str:
    resultado = _correr(["git", "status", "--porcelain"])
    sucio = [l for l in resultado.stdout.splitlines() if l.strip()]
    if sucio:
        detalle = ", ".join(l[3:] for l in sucio[:5])
        raise Fallo(
            f"el arbol tiene {len(sucio)} archivo(s) sin commitear: {detalle}. "
            "Commitea la tarea o revierte con `git reset --hard`."
        )
    return "arbol limpio"


def comprobar_sin_secretos() -> str:
    resultado = _correr(["git", "ls-files"])
    versionados = [l for l in resultado.stdout.splitlines() if l.strip()]
    filtrados = [
        f for f in versionados
        if Path(f).name == ".env" or (Path(f).name.startswith(".env.") and not f.endswith(".example"))
    ]
    if filtrados:
        raise Fallo(f"hay archivos de entorno versionados: {', '.join(filtrados)}. Sacalos del indice.")
    return f"{len(versionados)} archivos versionados, ningun .env"


def comprobar_suite() -> tuple[str, int]:
    resultado = _correr([_python(), "-m", "unittest", "discover", "-s", "tests"],
                        env=_entorno_mock())
    salida = resultado.stdout + resultado.stderr
    match = re.search(r"^Ran (\d+) tests?", salida, re.MULTILINE)
    if not match:
        raise Fallo("no se pudo leer el resultado de la suite; probablemente no llego a arrancar.")
    total = int(match.group(1))
    if resultado.returncode != 0:
        fallos = re.findall(r"^(FAIL|ERROR): (\S+)", salida, re.MULTILINE)
        detalle = ", ".join(f"{tipo} {nombre}" for tipo, nombre in fallos[:5]) or "ver salida"
        raise Fallo(f"la suite fallo ({total} tests): {detalle}")
    return f"{total} tests en verde", total


def comprobar_trinquete(total: int, piso_forzado: int | None) -> str:
    """El numero de tests no puede bajar nunca.

    Si baja, o se borro un test o se rompio el descubrimiento. Las dos cosas
    son inaceptables y las dos se ven igual desde aqui.
    """
    piso = piso_forzado
    if piso is None and ARCHIVO_PISO.exists():
        try:
            piso = int(ARCHIVO_PISO.read_text(encoding="utf-8").strip())
        except ValueError:
            piso = None
    if piso is not None and total < piso:
        raise Fallo(
            f"el numero de tests bajo de {piso} a {total}. Un test que estorba se arregla "
            "o se declara BLOQUEADA la tarea; nunca se borra ni se ablanda."
        )
    if piso is None or total > piso:
        ARCHIVO_PISO.parent.mkdir(parents=True, exist_ok=True)
        ARCHIVO_PISO.write_text(f"{total}\n", encoding="utf-8")
        return f"trinquete subido a {total}"
    return f"trinquete estable en {piso}"


def comprobar_flujo_mock() -> str:
    """El agente tiene que seguir corriendo de punta a punta sin tocar la nube."""
    resultado = _correr(
        [_python(), "scripts/ejecutablesBase/evaluar.py", "--mode", "mock"],
        env=_entorno_mock(),
    )
    if resultado.returncode != 0:
        cola = (resultado.stdout + resultado.stderr).strip().splitlines()[-3:]
        raise Fallo("el flujo en mock fallo: " + " / ".join(cola))
    return "flujo en mock ok"


def _entorno_mock() -> dict:
    import os
    entorno = dict(os.environ)
    entorno["MAAS_MODE"] = "mock"
    entorno.pop("MAAS_API_KEY", None)
    entorno["PYTHONIOENCODING"] = "utf-8"
    return entorno


def main() -> int:
    ap = argparse.ArgumentParser(description="Compuerta de verificacion nocturna")
    ap.add_argument("--rapida", action="store_true", help="salta el flujo en mock")
    ap.add_argument("--piso", type=int, help="fija el trinquete de tests a mano")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    pasos: list[tuple[str, str]] = []
    try:
        pasos.append(("arbol", comprobar_arbol_limpio()))
        pasos.append(("secretos", comprobar_sin_secretos()))
        detalle, total = comprobar_suite()
        pasos.append(("suite", detalle))
        pasos.append(("trinquete", comprobar_trinquete(total, args.piso)))
        if not args.rapida:
            pasos.append(("flujo-mock", comprobar_flujo_mock()))
    except Fallo as error:
        if args.json:
            print(json.dumps({"ok": False, "motivo": str(error),
                              "pasos": [{"paso": p, "detalle": d} for p, d in pasos]},
                             ensure_ascii=False))
        else:
            for paso, detalle in pasos:
                print(f"  ok   {paso:<12} {detalle}")
            print(f"  FALLA {'':<11} {error}")
        return 1

    if args.json:
        print(json.dumps({"ok": True, "pasos": [{"paso": p, "detalle": d} for p, d in pasos]},
                         ensure_ascii=False))
    else:
        for paso, detalle in pasos:
            print(f"  ok   {paso:<12} {detalle}")
        print("\nCOMPUERTA VERDE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
