"""Estimación de variación de coste. Aritmética pura: nunca gasta un turno de LLM."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .diff import added_lines, removed_lines


CATALOG_PATH = Path(__file__).parent / "policies" / "flavors.json"
REPLICAS_PATTERN = re.compile(r"replicas\s*[:=]\s*(\d+)", re.IGNORECASE)


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _first_match(lines: list[str], pattern: re.Pattern[str]) -> str | None:
    for line in lines:
        found = pattern.search(line)
        if found:
            return found.group(1)
    return None


def _side_cost(lines: list[str], catalog: dict[str, Any]) -> tuple[float, str | None, int | None]:
    flavor_pattern = re.compile(catalog["flavor_pattern"], re.IGNORECASE)

    flavor = _first_match(lines, flavor_pattern)
    raw_replicas = _first_match(lines, REPLICAS_PATTERN)
    replicas = int(raw_replicas) if raw_replicas else None

    units = catalog["units"].get(flavor, catalog["default_units"]) if flavor else None

    if units is None and replicas is None:
        return 0.0, None, None

    return (units or catalog["default_units"]) * (replicas or 1), flavor, replicas


def estimate_cost(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Compara el coste relativo antes y después del cambio.

    Las unidades son relativas a `c7.large = 1`; miden la variación, no
    el importe facturado, que depende de región y compromiso.
    """
    catalog = load_catalog()

    before: list[str] = []
    after: list[str] = []
    for item in files:
        patch = item.get("patch") or ""
        before.extend(removed_lines(patch))
        after.extend(added_lines(patch))

    previous, previous_flavor, previous_replicas = _side_cost(before, catalog)
    estimated, new_flavor, new_replicas = _side_cost(after, catalog)

    if previous <= 0 or estimated <= 0:
        return {
            "applicable": False,
            "reason": "El cambio no declara instancias ni réplicas comparables.",
        }

    return {
        "applicable": True,
        "previous_cost": round(previous, 2),
        "estimated_cost": round(estimated, 2),
        "increase_percent": round((estimated - previous) / previous * 100),
        "previous": {"flavor": previous_flavor, "replicas": previous_replicas},
        "current": {"flavor": new_flavor, "replicas": new_replicas},
    }
