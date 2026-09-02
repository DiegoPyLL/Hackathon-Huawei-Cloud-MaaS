"""Publicación del veredicto en el Pull Request."""

from __future__ import annotations

import pytest

from guardian import publish
from guardian.github import GitHubHTTPError


BASE_REPORT = {
    "repository": "owner/repo",
    "environment": "production",
    "mode": "live",
    "decision": "BLOCK",
    "risk_score": 50,
    "findings": [
        {
            "type": "HARDCODED_SECRET",
            "severity": "CRITICAL",
            "file": ".env",
            "message": "Credencial detectada en la configuración.",
            "policy": "POLICY-SEC-002",
            "source": "rule_engine",
        }
    ],
    "cost": {"applicable": True, "previous_cost": 2, "estimated_cost": 640, "increase_percent": 31900},
    "savings": {"files_total": 26, "files_selected": 7, "full_diff_tokens": 6072, "context_tokens": 2514},
    "budget": {"llm_calls": 1, "tool_calls": 0},
}


class FakeGitHub:
    """Registra las peticiones y responde como la API real."""

    def __init__(self, comments: list | None = None, labels: list | None = None) -> None:
        self.comments = comments if comments is not None else []
        self.labels = labels if labels is not None else []
        self.calls: list[tuple[str, str]] = []

    def __call__(self, url, token, *, method="GET", data=None):
        self.calls.append((method, url))

        if method == "GET" and "/comments" in url:
            return self.comments
        if method == "GET":
            return {"labels": self.labels}
        if method == "POST" and "/comments" in url:
            return {"html_url": "https://github.com/owner/repo/pull/3#issuecomment-1"}
        if method == "PATCH":
            return {"html_url": "https://github.com/owner/repo/pull/3#issuecomment-9"}
        return {}


@pytest.fixture
def fake(monkeypatch):
    stub = FakeGitHub()
    monkeypatch.setattr(publish, "github_request", stub)
    return stub


def test_sin_token_no_publica_ni_falla():
    result = publish.publish(BASE_REPORT, 3, None)

    assert result == {"published": False, "reason": "No hay GITHUB_TOKEN para escribir."}


def test_publica_comentario_y_etiqueta(fake):
    result = publish.publish(BASE_REPORT, 3, "token")

    assert result["published"] is True
    assert result["comment_action"] == "created"
    assert result["label"] == "guardian:block"


def test_el_comentario_se_actualiza_en_lugar_de_duplicarse(monkeypatch):
    stub = FakeGitHub(comments=[{"id": 77, "body": f"{publish.MARKER}\nviejo"}])
    monkeypatch.setattr(publish, "github_request", stub)

    result = publish.publish(BASE_REPORT, 3, "token")

    assert result["comment_action"] == "updated"
    assert any(method == "PATCH" for method, _ in stub.calls)
    assert not any(method == "POST" and "/comments" in url for method, url in stub.calls)


def test_se_retira_la_etiqueta_de_un_veredicto_anterior(monkeypatch):
    stub = FakeGitHub(labels=[{"name": "guardian:approve"}, {"name": "documentacion"}])
    monkeypatch.setattr(publish, "github_request", stub)

    publish.publish(BASE_REPORT, 3, "token")
    borrados = [url for method, url in stub.calls if method == "DELETE"]

    assert any(url.endswith("/labels/guardian:approve") for url in borrados)
    assert not any("documentacion" in url for url in borrados)


def test_una_etiqueta_ya_existente_no_se_vuelve_a_aplicar(monkeypatch):
    stub = FakeGitHub(labels=[{"name": "guardian:block"}])
    monkeypatch.setattr(publish, "github_request", stub)

    publish.publish(BASE_REPORT, 3, "token")

    assert not any(method == "DELETE" for method, _ in stub.calls)
    assert not any(
        method == "POST" and url.endswith("/issues/3/labels") for method, url in stub.calls
    )


def test_que_la_etiqueta_ya_exista_en_el_repo_no_es_un_error(monkeypatch):
    stub = FakeGitHub()
    original = stub.__call__

    def rechaza_creacion(url, token, *, method="GET", data=None):
        if method == "POST" and url.endswith("/labels") and data and "color" in data:
            raise GitHubHTTPError("ya existe", 422)
        return original(url, token, method=method, data=data)

    monkeypatch.setattr(publish, "github_request", rechaza_creacion)

    assert publish.publish(BASE_REPORT, 3, "token")["published"] is True


def test_un_fallo_de_permisos_no_invalida_el_analisis(monkeypatch):
    def sin_permisos(*args, **kwargs):
        raise GitHubHTTPError("Acceso denegado por GitHub.", 403)

    monkeypatch.setattr(publish, "github_request", sin_permisos)
    result = publish.publish(BASE_REPORT, 3, "token")

    assert result["published"] is False
    assert "denegado" in result["reason"]


def test_el_comentario_no_reproduce_el_valor_del_secreto():
    body = publish.render_comment(BASE_REPORT)

    assert "DESPLIEGUE BLOQUEADO" in body
    assert publish.MARKER in body
    assert "`.env`" in body
    assert "sk-" not in body


def test_el_comentario_muestra_el_presupuesto_y_el_modo():
    body = publish.render_comment(BASE_REPORT)

    assert "`live`" in body
    assert "2514" in body
    assert "7 de 26" in body


def test_un_veredicto_sin_hallazgos_lo_dice_explicitamente():
    body = publish.render_comment({**BASE_REPORT, "decision": "APPROVE", "findings": []})

    assert "APROBADO" in body
    assert "No se detectaron riesgos" in body
