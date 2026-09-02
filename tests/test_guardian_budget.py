"""El recorte de contexto es medible, no una afirmación de marketing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from guardian.analyzer import analyze_payload
from guardian.context import build_analysis_context


FIXTURE = Path(__file__).parent / "fixtures" / "pr_3.json"
MAX_CONTEXT_TOKENS = 6_000


@pytest.fixture(scope="module")
def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class SilentProvider:
    """No aporta hallazgos: aísla lo que hacen las reglas deterministas."""

    def stream(self, messages):
        yield {"type": "delta", "delta": '{"action": "findings", "findings": []}'}
        yield {"type": "done", "mode": "mock"}


def test_el_contexto_cabe_en_el_presupuesto(payload):
    savings = build_analysis_context(payload)["savings"]

    assert savings["context_tokens"] < MAX_CONTEXT_TOKENS


def test_el_filtro_recorta_frente_al_diff_completo(payload):
    savings = build_analysis_context(payload)["savings"]

    assert savings["files_selected"] < savings["files_total"]
    assert savings["context_tokens"] < savings["full_diff_tokens"] / 2


def test_la_brecha_de_seguridad_bloquea_el_despliegue(payload):
    report = analyze_payload(payload, provider=SilentProvider(), mode="mock")
    secretos = [item for item in report["findings"] if item["type"] == "HARDCODED_SECRET"]

    assert report["decision"] == "BLOCK"
    assert [item["file"] for item in secretos] == [".env"]
    assert report["suggested_action"] == "GENERATE_PATCH"


def test_el_modo_de_ejecucion_siempre_viaja_en_la_respuesta(payload):
    report = analyze_payload(payload, provider=SilentProvider(), mode="mock")

    assert report["mode"] == "mock"
    assert report["budget"]["llm_calls"] == 1
