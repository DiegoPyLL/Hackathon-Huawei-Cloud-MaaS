"""Lectura de las líneas de un patch unificado."""

from __future__ import annotations

from collections.abc import Iterator


def _lines(patch: str, marker: str) -> Iterator[str]:
    for line in patch.splitlines():
        # '+++' y '---' son cabeceras del patch, no contenido.
        if line.startswith(marker) and not line.startswith(marker * 3):
            yield line[1:]


def added_lines(patch: str) -> list[str]:
    """Líneas que el Pull Request introduce."""
    return list(_lines(patch, "+"))


def removed_lines(patch: str) -> list[str]:
    """Líneas que el Pull Request elimina."""
    return list(_lines(patch, "-"))
