"""
Base de conocimiento de incidentes previos + retrieval simple por keywords.

No usamos embeddings (no hay tiempo en 6h de hackathon para eso). En su lugar,
retrieval por coincidencia de servicio + categoría + overlap de palabras clave.
Suficiente para la demo de RAG: "esto ya pasó, así se arregló".
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .schema import Categoria, IncidentePrevioRef

STOPWORDS = {
    "el", "la", "los", "las", "de", "del", "y", "o", "a", "en", "que", "es",
    "se", "un", "una", "con", "por", "para", "como", "mas", "muy", "ya",
    "no", "si", "the", "is", "at", "on", "in", "to", "a", "an", "of",
    "and", "or", "for", "with", "by", "from", "it", "this", "that",
}

_PALABRA_RE = re.compile(r"[a-záéíóúñ]{3,}", re.IGNORECASE)


def tokenize(texto: str) -> set[str]:
    return {w.lower() for w in _PALABRA_RE.findall(texto) if w.lower() not in STOPWORDS}


class KnowledgeBase:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.incidents: list[dict] = []
        self._index: list[tuple[set[str], dict]] = []
        self.load()

    def load(self):
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    inc = json.loads(line)
                    self.incidents.append(inc)
                    tokens = tokenize(inc.get("resumen", "") + " " + inc.get("causa_raiz", ""))
                    tokens.add(inc.get("servicio", ""))
                    self._index.append((tokens, inc))

    def search(
        self,
        query: str,
        servicio: str | None = None,
        categoria: Categoria | None = None,
        top_k: int = 3,
    ) -> list[IncidentePrevioRef]:
        query_tokens = tokenize(query)
        if servicio:
            query_tokens.add(servicio)

        scored: list[tuple[float, dict]] = []
        for tokens, inc in self._index:
            if servicio and inc.get("servicio") != servicio:
                continue
            if categoria and inc.get("categoria") != categoria.value:
                continue

            if not query_tokens or not tokens:
                overlap = 0.0
            else:
                overlap = len(query_tokens & tokens) / len(query_tokens | tokens)

            if overlap > 0:
                scored.append((overlap, inc))

        scored.sort(key=lambda x: -x[0])

        results: list[IncidentePrevioRef] = []
        for score, inc in scored[:top_k]:
            results.append(IncidentePrevioRef(
                id=inc["id"],
                resumen=inc.get("resumen", ""),
                causa_raiz=inc.get("causa_raiz", ""),
                solucion=inc.get("solucion", ""),
                fecha=inc.get("fecha", ""),
                score=round(score, 3),
            ))
        return results
