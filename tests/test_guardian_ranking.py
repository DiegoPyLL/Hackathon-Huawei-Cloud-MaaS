"""El índice de importancia decide qué archivos cuestan tokens."""

from __future__ import annotations

from guardian.context import build_analysis_context
from guardian.ranking import build_report, load_rules, priority


def _file(name: str, changes: int = 10, status: str = "modified") -> dict:
    return {
        "filename": name,
        "status": status,
        "changes": changes,
        "additions": changes,
        "deletions": 0,
        "patch": f"@@ -1 +1 @@\n+linea de {name}\n",
    }


def test_env_pequeno_supera_a_lockfile_enorme():
    """La escala logarítmica evita que el tamaño eclipse a lo crítico."""
    report = build_report(
        {"files": [_file(".env", changes=3), _file("package-lock.json", changes=2000)]}
    )
    ranked = {item["filename"]: item["importance_index"] for item in report["files_by_importance"]}

    assert ranked[".env"] > ranked["package-lock.json"]


def test_binarios_generados_quedan_fuera_de_la_cola():
    report = build_report({"files": [_file("src/__pycache__/x.cpython-314.pyc")]})

    assert report["llm_analysis_queue"] == []


def test_documentacion_no_llega_al_llm():
    report = build_report({"files": [_file("docs/architecture/stack.md")]})

    assert report["llm_analysis_queue"] == []


def test_infraestructura_es_critica():
    report = build_report({"files": [_file("terraform/main.tf")]})

    assert report["files_by_importance"][0]["priority"] == "CRITICAL"


def test_priority_respeta_las_bandas():
    rules = load_rules()

    assert priority(90, rules) == "CRITICAL"
    assert priority(70, rules) == "HIGH"
    assert priority(50, rules) == "MEDIUM"
    assert priority(10, rules) == "MINIMAL"


def test_el_contexto_solo_contiene_archivos_seleccionados():
    payload = {"files": [_file("terraform/main.tf"), _file("docs/nota.md")]}
    prepared = build_analysis_context(payload)

    assert "terraform/main.tf" in prepared["context"]
    assert "docs/nota.md" not in prepared["context"]
    assert prepared["savings"]["files_total"] == 2
    assert prepared["savings"]["files_selected"] == 1
