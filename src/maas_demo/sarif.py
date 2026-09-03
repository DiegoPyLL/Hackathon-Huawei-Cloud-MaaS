"""Traduce los hallazgos del agente a SARIF 2.1.0 para GitHub code scanning.

El [ADR-0009](../../docs/architecture/decisions/0009-salida-como-code-scanning.md)
eligió code scanning y no un Security Advisory real. Este módulo es la frontera:
convierte el resultado del `Orchestrator` en el documento que sube el workflow,
sin conocer nada de GitHub ni de HTTP.

Dos decisiones que sostienen el resto:

- El catálogo de reglas son los 8 tipos canónicos, importados de `orchestrator`.
  La taxonomía vive en un solo sitio.
- Cada resultado lleva `partialFingerprints`. Sin ellos, un cron diario abriría
  alertas nuevas cada noche en vez de mantener abiertas las mismas.
"""

from __future__ import annotations

from typing import Any

from .orchestrator import TYPES


SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
HERRAMIENTA = "Incident Response Agent"
REPOSITORIO = "https://github.com/DiegoPyLL/Hackathon-Huawei-Cloud-MaaS"

# La severidad del incidente decide cómo se ve la alerta. `security-severity`
# es el número con el que GitHub la clasifica en Critical/High/Medium/Low.
NIVEL = {"critica": "error", "alta": "error", "media": "warning", "baja": "note"}
PUNTAJE = {"critica": "9.0", "alta": "7.0", "media": "5.0", "baja": "3.0"}

REGLAS = tuple(sorted(TYPES))


def _regla(tipo: str) -> dict[str, Any]:
    legible = tipo.replace("-", " ").capitalize()
    return {
        "id": tipo,
        "name": tipo.replace("-", "_"),
        "shortDescription": {"text": legible},
        "fullDescription": {
            "text": f"Incidente de tipo {legible}, clasificado por el agente sobre "
            "la taxonomía canónica de 8 tipos."
        },
        "defaultConfiguration": {"level": "warning"},
        "properties": {"tags": ["incident-response", tipo]},
    }


def _texto(incidente: dict[str, Any], hallazgo: dict[str, Any]) -> str:
    """El mensaje de la alerta. Nunca una causa raíz sin la evidencia que la sostiene."""
    lineas = [f"{incidente['id']} · {incidente['titulo']}"]
    if hallazgo.get("estado") == "fallido":
        lineas.append(f"El especialista {hallazgo['especialista']} falló: {hallazgo.get('error', 'sin detalle')}.")
        return "\n".join(lineas)

    lineas.append(f"Causa raíz ({hallazgo['especialista']}, confianza {hallazgo.get('confianza', 'no declarada')}): "
                  f"{hallazgo.get('causa_raiz', 'no propuesta')}")
    for cita in hallazgo.get("evidencia", []):
        lineas.append(f"  Evidencia: {cita}")
    for descartado in hallazgo.get("descartado", []):
        lineas.append(f"  Descartado: {descartado}")
    if hallazgo.get("viabilidad"):
        lineas.append(f"  Viabilidad: {hallazgo['viabilidad']}")
    if incidente.get("ataque_activo"):
        lineas.append("  Señalado como ataque activo por el triage.")
    return "\n".join(lineas)


def _resultado(corrida: dict[str, Any], incidente: dict[str, Any], hallazgo: dict[str, Any],
               inventario: str) -> dict[str, Any]:
    severidad = incidente["severidad"]
    return {
        "ruleId": incidente["tipo"],
        "ruleIndex": REGLAS.index(incidente["tipo"]),
        "level": NIVEL[severidad],
        "message": {"text": _texto(incidente, hallazgo)},
        "locations": [{
            "physicalLocation": {
                "artifactLocation": {"uri": inventario},
                "region": {"startLine": max(1, int(corrida.get("linea", 1)))},
            }
        }],
        # Identidad estable del hallazgo: el mismo incidente visto por el mismo
        # especialista es la misma alerta, corrida tras corrida.
        "partialFingerprints": {"incidente": f"{corrida['origen']}/{hallazgo['especialista']}"},
        "properties": {
            "security-severity": PUNTAJE[severidad],
            "severidad": severidad,
            "canal": incidente["canal"],
            "corrida": corrida["run_id"],
        },
    }


def construir_sarif(corridas: list[dict[str, Any]], *,
                    inventario: str = "evals/results/incidentes-supabase.jsonl") -> dict[str, Any]:
    """Documento SARIF con un resultado por hallazgo de cada corrida.

    Cada corrida es el resultado del `Orchestrator`, más `origen` (la fila de
    Supabase que la originó) y `linea` (su posición en el inventario).
    """
    resultados: list[dict[str, Any]] = []
    for corrida in corridas:
        incidentes = {i["id"]: i for i in corrida.get("triage", {}).get("incidentes", [])}
        for hallazgo in corrida.get("hallazgos", []):
            incidente = incidentes.get(hallazgo["incidente_id"])
            if incidente is None:
                continue
            resultados.append(_resultado(corrida, incidente, hallazgo, inventario))

    return {
        "$schema": SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": HERRAMIENTA,
                "informationUri": REPOSITORIO,
                "rules": [_regla(tipo) for tipo in REGLAS],
            }},
            "results": resultados,
        }],
    }
