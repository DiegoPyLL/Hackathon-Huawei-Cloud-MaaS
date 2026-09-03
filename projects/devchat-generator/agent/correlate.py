"""
Correlación y deduplicación cross-canal.

Dos incidentes consolidados se consideran duplicados si:
  - Ambos son incidentes reales (es_incidente=True, categoría en la taxonomía).
  - Mismo servicio afectado.
  - Misma categoría.
  - Timestamps dentro de una ventana de tiempo (default 30 min).

El segundo se marca como duplicado del primero (duplicado_de = primer_id).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from .schema import IncidenteConsolidado, CATEGORIAS_INCIDENTE


def correlacionar(
    incidentes: list[IncidenteConsolidado],
    ventana_minutos: int = 30,
) -> list[IncidenteConsolidado]:
    incidentes_sorted = sorted(incidentes, key=lambda i: i.timestamp)
    ventana = timedelta(minutes=ventana_minutos)

    for i, inc in enumerate(incidentes_sorted):
        if not inc.es_incidente_real():
            continue
        if inc.duplicado_de:
            continue

        for j in range(i + 1, len(incidentes_sorted)):
            otro = incidentes_sorted[j]
            if not otro.es_incidente_real():
                continue
            if otro.duplicado_de:
                continue
            if otro.timestamp - inc.timestamp > ventana:
                break

            if (
                inc.servicio_afectado
                and inc.servicio_afectado == otro.servicio_afectado
                and inc.categoria == otro.categoria
            ):
                otro.duplicado_de = inc.id

    return incidentes_sorted


def estadisticas(incidentes: list[IncidenteConsolidado]) -> dict:
    total = len(incidentes)
    incidentes_reales = [i for i in incidentes if i.es_incidente_real()]
    duplicados = [i for i in incidentes if i.duplicado_de]
    por_categoria: dict[str, int] = {}
    por_severidad: dict[str, int] = {}
    por_canal: dict[str, int] = {}

    for inc in incidentes_reales:
        if inc.duplicado_de:
            continue
        cat = inc.categoria.value
        por_categoria[cat] = por_categoria.get(cat, 0) + 1
        sev = inc.severidad.value
        por_severidad[sev] = por_severidad.get(sev, 0) + 1
        canal = inc.canal_origen.value
        por_canal[canal] = por_canal.get(canal, 0) + 1

    return {
        "total_senales": total,
        "incidentes_reales": len(incidentes_reales) - len(duplicados),
        "duplicados_detectados": len(duplicados),
        "no_incidentes": total - len(incidentes_reales),
        "por_categoria": por_categoria,
        "por_severidad": por_severidad,
        "por_canal": por_canal,
    }
