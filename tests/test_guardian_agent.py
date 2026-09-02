"""El bucle del agente respeta su presupuesto."""

from __future__ import annotations

import json

from guardian.agent import analyze, extract_json, normalize_findings
from guardian.budget import Budget


class ScriptedProvider:
    """Devuelve respuestas predefinidas, una por llamada."""

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.calls = 0

    def stream(self, messages):
        self.calls += 1
        answer = self.answers[min(self.calls - 1, len(self.answers) - 1)]
        yield {"type": "delta", "delta": answer}
        yield {"type": "done", "mode": "mock", "usage": {"total_tokens": 10}}


def _need(*files: str) -> str:
    return json.dumps({"action": "need_files", "files": list(files), "reason": "falta contexto"})


FINDINGS = json.dumps(
    {
        "action": "findings",
        "findings": [
            {"type": "PUBLIC_SSH", "severity": "HIGH", "file": "a.tf", "message": "expuesto"}
        ],
    }
)


def test_devuelve_los_hallazgos_del_modelo():
    budget = Budget()
    result = analyze("diff", provider=ScriptedProvider(FINDINGS), budget=budget)

    assert result["findings"][0]["type"] == "PUBLIC_SSH"
    assert result["findings"][0]["source"] == "llm"
    assert budget.llm_calls == 1


def test_el_bucle_corta_al_agotar_las_tool_calls():
    provider = ScriptedProvider(_need("a.tf"), _need("b.tf"), _need("c.tf"), FINDINGS)
    budget = Budget(max_tool_calls=2)

    analyze("diff", provider=provider, budget=budget, read_file=lambda name: f"contenido {name}")

    assert budget.tool_calls == 2


def test_una_relectura_del_mismo_archivo_se_rechaza():
    provider = ScriptedProvider(_need("a.tf"), _need("a.tf"), FINDINGS)
    budget = Budget()
    reads: list[str] = []

    def read(name: str) -> str:
        reads.append(name)
        return "contenido"

    result = analyze("diff", provider=provider, budget=budget, read_file=read)

    assert reads == ["a.tf"]
    assert any("Relectura rechazada" in note for note in result["notes"])


def test_una_respuesta_sin_json_no_aporta_hallazgos():
    result = analyze("diff", provider=ScriptedProvider("lo siento, texto libre"), budget=Budget())

    assert result["findings"] == []
    assert result["notes"]


def test_un_fallo_de_lectura_no_aborta_el_analisis():
    provider = ScriptedProvider(_need("secreto.tf"), FINDINGS)

    def read(name: str) -> str:
        raise PermissionError("sin acceso")

    result = analyze("diff", provider=provider, budget=Budget(), read_file=read)

    assert result["findings"][0]["type"] == "PUBLIC_SSH"
    assert any("No se pudo leer" in note for note in result["notes"])


def test_extract_json_tolera_ruido_alrededor():
    assert extract_json('Claro:\n```json\n{"action": "findings"}\n```')["action"] == "findings"
    assert extract_json("sin json") is None


def test_se_descartan_los_hallazgos_mal_formados():
    payload = {
        "findings": [
            {"severity": "INVENTADA", "message": "x"},
            {"severity": "HIGH"},
            {"severity": "LOW", "message": "válido"},
        ]
    }

    assert len(normalize_findings(payload)) == 1


def test_el_presupuesto_acumula_el_usage_reportado():
    budget = Budget()
    analyze("diff", provider=ScriptedProvider(FINDINGS), budget=budget)

    assert budget.report()["reported_usage"] == {"total_tokens": 10}
