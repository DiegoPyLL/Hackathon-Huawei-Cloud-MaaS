#!/usr/bin/env python3
"""Puntuacion repetible del agente sobre varios escenarios del bus.

Una corrida suelta no dice nada: el modelo varia y un buen resultado puede ser
suerte. Esto provoca N escenarios distintos, dispara una corrida por cada uno y
agrega las metricas, para poder decir "acierta el tipo el 80% de las veces" con
un numero detras en vez de una impresion.

Requiere el stack levantado:

    python projects/bus-incidentes/levantar_todo.py --mock

y despues:

    python scripts/ejecutablesBase/puntuar.py --escenarios 6
    python scripts/ejecutablesBase/puntuar.py --escenarios 6 --json-out evals/results/score.json

UNA ADVERTENCIA SOBRE LO QUE MIDE CADA FILA
-------------------------------------------
El bus no tiene reset: un incidente vive 3-6 minutos hasta que se resuelve solo.
Asi que la corrida de la fila N ve el escenario que se acaba de provocar Y los
que siguen vivos de las filas anteriores. Cada fila se etiqueta con el escenario
que la disparo, pero puntua contra TODO lo que estaba activo, que es exactamente
lo que el agente vio. Es lo honesto: inventar una atribucion por escenario seria
mentir sobre lo que se midio.

Por eso la fila TOTAL no es el promedio de las filas: se recalcula sobre la suma
de los incidentes de todas las corridas.

Una corrida que falla sale como fallo y no se promedia hacia fuera: un error no
puede mejorar la media por desaparecer de ella.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "projects" / "agente-puente"))

import puente  # noqa: E402
from trazabilidad import construir_linaje, construir_ruido, puntuar  # noqa: E402

# Escenarios variados a proposito: si se puntuara solo sobre caidas tras deploy
# el numero diria poco. Estos tocan disponibilidad, identidad, datos, capacidad,
# seguridad e integracion con terceros.
ESCENARIOS_POR_DEFECTO = [
    "caida_tras_deploy",
    "bloqueo_cuenta_masivo",
    "latencia_por_locks",
    "disco_motor_datos",
    "credential_stuffing_horizontal",
    "webhook_partner_caido",
]

METRICAS = [
    ("precision", "precision"),
    ("recall", "recall"),
    ("f1", "f1"),
    ("exactitud_tipo", "tipo"),
    ("exactitud_severidad", "severidad"),
    ("exactitud_ruteo", "ruteo"),
    ("accion_correcta", "accion"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Puntua al agente sobre varios escenarios.")
    parser.add_argument("--escenarios", type=int, default=len(ESCENARIOS_POR_DEFECTO),
                        help="cuantos escenarios provocar (por orden de la lista)")
    parser.add_argument("--lista", nargs="*", help="escenarios concretos, por nombre")
    parser.add_argument("--espera", type=float, default=3.0,
                        help="segundos entre provocar y correr, para que los canales publiquen")
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def provocar(escenario: str) -> dict | None:
    cuerpo = json.dumps({"escenario": escenario}).encode()
    peticion = urllib.request.Request(
        f"{puente.BUS_URL}/api/incidentes/provocar", data=cuerpo,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:
            return json.load(respuesta)
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None


def puntuar_corrida(resultado: dict) -> dict | None:
    """Saca la puntuacion de una corrida del puente. None si la corrida fallo."""
    agente = resultado.get("agente") or {}
    if agente.get("error") or not agente.get("triage"):
        return None
    verdad = resultado.get("_verdad") or {}
    canales = resultado.get("_canales") or {}
    linaje = construir_linaje(verdad, agente["triage"], agente.get("hallazgos", []), canales)
    falsos = construir_ruido(verdad, agente["triage"], canales)["falsos_positivos"]
    return puntuar(linaje, falsos) | {"_linaje": linaje}


def formatear(valor: float | None) -> str:
    return "   n/a" if valor is None else f"{valor:>5.0%}"


def imprimir_tabla(filas: list[dict], total: dict | None) -> None:
    cabecera = f"{'escenario':<32} {'inc':>4} " + " ".join(f"{n:>9}" for _, n in METRICAS)
    print(cabecera)
    print("-" * len(cabecera))
    for fila in filas:
        if fila["puntuacion"] is None:
            print(f"{fila['escenario']:<32} {'—':>4}  CORRIDA FALLIDA: {fila['motivo'][:60]}")
            continue
        p = fila["puntuacion"]
        valores = " ".join(f"{formatear(p[clave]):>9}" for clave, _ in METRICAS)
        print(f"{fila['escenario']:<32} {p['incidentes_reales']:>4} {valores}")
    if total:
        print("-" * len(cabecera))
        valores = " ".join(f"{formatear(total[clave]):>9}" for clave, _ in METRICAS)
        print(f"{'TOTAL':<32} {total['incidentes_reales']:>4} {valores}")


def main() -> int:
    args = parse_args()
    escenarios = args.lista or ESCENARIOS_POR_DEFECTO[:args.escenarios]
    if not escenarios:
        print("No hay escenarios que puntuar.")
        return 2

    filas: list[dict] = []
    linaje_acumulado: list[dict] = []
    falsos_acumulados = 0

    for escenario in escenarios:
        provocado = provocar(escenario)
        if provocado is None:
            filas.append({"escenario": escenario, "puntuacion": None,
                          "motivo": "el bus no acepto el escenario (¿esta levantado?)"})
            continue
        time.sleep(args.espera)

        canales = puente.recoger_evidencia()
        volcado = puente.armar_volcado(canales)
        verdad = puente._get(f"{puente.BUS_URL}/api/verdad") or {}
        agente = puente.preguntar_al_agente(volcado)

        resultado = {"agente": agente, "_verdad": verdad, "_canales": canales}
        puntos = puntuar_corrida(resultado)
        if puntos is None:
            filas.append({"escenario": escenario, "puntuacion": None,
                          "motivo": agente.get("error") or "el triage no entrego nada"})
            continue

        linaje_acumulado.extend(puntos.pop("_linaje"))
        falsos_acumulados += puntos["falsos_positivos"]
        filas.append({"escenario": escenario, "puntuacion": puntos,
                      "meta": agente.get("meta", {})})

    # El TOTAL se recalcula sobre todos los incidentes, no se promedian las
    # filas: promediar porcentajes de denominadores distintos da un numero que
    # no significa nada.
    total = puntuar(linaje_acumulado, falsos_acumulados) if linaje_acumulado else None

    print()
    imprimir_tabla(filas, total)
    fallidas = [f for f in filas if f["puntuacion"] is None]
    print()
    print(f"corridas: {len(filas)} · fallidas: {len(fallidas)}")
    if fallidas:
        print("Las corridas fallidas NO entran en el TOTAL y no lo mejoran por desaparecer.")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(
            {"filas": [{k: v for k, v in f.items() if not k.startswith("_")} for f in filas],
             "total": total, "fallidas": len(fallidas)},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"guardado en {args.json_out}")

    # Que haya corridas fallidas es un resultado, no un error del script.
    return 1 if len(fallidas) == len(filas) else 0


if __name__ == "__main__":
    raise SystemExit(main())
