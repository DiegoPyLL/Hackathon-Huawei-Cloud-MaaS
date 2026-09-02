"""El Rule Engine controla las reglas no negociables."""

from __future__ import annotations

import pytest

from guardian import cost, policy


# Configuración del ejemplo del eval (AI_Cloud_Deployment_Guardian.md).
EVAL_PATCH = """@@ -1,4 +1,9 @@
-  flavor: c7.large
-replicas: 2
+  flavor: c7.16xlarge
+replicas: 20
+environment:
+  DB_PASSWORD: "supersecret123"
+security_group:
+  ingress:
+    - 0.0.0.0/0
+database_public_access: true
"""

EVAL_FILES = [{"filename": "infra/produccion.yaml", "patch": EVAL_PATCH}]


def test_el_ejemplo_del_eval_produce_los_cuatro_hallazgos():
    findings = policy.evaluate(EVAL_FILES)
    tipos = {item["type"] for item in findings}

    assert tipos == {
        "PUBLIC_DATABASE",
        "PUBLIC_SSH",
        "HARDCODED_SECRET",
        "EXCESSIVE_REPLICAS",
    }


def test_el_ejemplo_del_eval_bloquea_el_despliegue():
    findings = policy.evaluate(EVAL_FILES)
    findings += policy.cost_finding(cost.estimate_cost(EVAL_FILES))
    score = policy.risk_score(findings)

    assert score == 100
    assert policy.decide(score, findings) == "BLOCK"


def test_una_credencial_filtrada_bloquea_por_si_sola():
    """50 puntos no alcanzan la banda de BLOCK: el CRITICAL manda igualmente."""
    files = [{"filename": ".env", "patch": "@@ -0,0 +1 @@\n+MAAS_API_KEY=sk-ufonr2rwXUG5fjN\n"}]
    findings = policy.evaluate(files)

    assert [item["type"] for item in findings] == ["HARDCODED_SECRET"]
    assert policy.decide(policy.risk_score(findings), findings) == "BLOCK"


def test_una_variable_de_codigo_no_es_una_credencial():
    files = [{"filename": "app.py", "patch": "@@ -1 +1 @@\n+    token=token,\n"}]

    assert policy.evaluate(files) == []


def test_una_referencia_a_gestor_de_secretos_no_es_una_credencial():
    files = [{"filename": "infra/x.yaml", "patch": '@@ -1 +1 @@\n+  DB_PASSWORD: ${DB_SECRET}\n'}]

    assert policy.evaluate(files) == []


def test_el_entorno_de_desarrollo_relaja_las_reglas_de_red():
    files = [{"filename": "infra/dev.yaml", "patch": "@@ -1 +1 @@\n+    - 0.0.0.0/0\n"}]

    assert policy.evaluate(files, "production")
    assert policy.evaluate(files, "development") == []


def test_un_entorno_desconocido_falla_de_forma_explicita():
    with pytest.raises(policy.PolicyError, match="desconocido"):
        policy.evaluate(EVAL_FILES, "inexistente")


def test_el_coste_se_calcula_sin_llamar_al_modelo():
    estimate = cost.estimate_cost(EVAL_FILES)

    assert estimate["previous_cost"] == 2
    assert estimate["estimated_cost"] == 640
    assert estimate["increase_percent"] == 31900


def test_sin_instancias_declaradas_el_coste_no_aplica():
    files = [{"filename": "README.md", "patch": "@@ -1 +1 @@\n+texto\n"}]

    assert cost.estimate_cost(files)["applicable"] is False
