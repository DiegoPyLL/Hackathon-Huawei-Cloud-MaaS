"""Contrato público de la API FastAPI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from maas_demo.api import create_app
from maas_demo.config import Config


@pytest.fixture(scope="module")
def client() -> TestClient:
    config = Config(mode="mock", api_key=None, base_url="https://x/v1", model="mock-model")
    return TestClient(create_app(config))


def test_health_expone_el_modo_de_ejecucion(client):
    body = client.get("/api/health").json()

    assert body == {"status": "ok", "mode": "mock", "model": "mock-model"}


def test_las_cabeceras_de_seguridad_viajan_en_cada_respuesta(client):
    headers = client.get("/api/health").headers

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["cache-control"] == "no-store"
    assert "default-src 'self'" in headers["content-security-policy"]


def test_el_chat_devuelve_un_stream_de_eventos(client):
    response = client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "hola"}]})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data:" in response.text


def test_un_mensaje_con_rol_invalido_se_rechaza(client):
    response = client.post("/api/chat/stream", json={"messages": [{"role": "root", "content": "x"}]})

    assert response.status_code == 422


def test_el_repositorio_debe_tener_formato_owner_repo(client):
    response = client.post("/api/guardian/analyze", json={"repository": "suelto", "pr": 1})

    assert response.status_code == 422


def test_el_numero_de_pull_request_debe_ser_positivo(client):
    response = client.post(
        "/api/guardian/analyze", json={"repository": "owner/repo", "pr": 0}
    )

    assert response.status_code == 422


def test_un_entorno_desconocido_devuelve_400(client, monkeypatch):
    monkeypatch.setattr(
        "maas_demo.api.build_payload",
        lambda *args, **kwargs: {"repository": "owner/repo", "files": [], "pull_request": {}},
    )
    response = client.post(
        "/api/guardian/analyze",
        json={"repository": "owner/repo", "pr": 1, "environment": "inexistente"},
    )

    assert response.status_code == 400


def test_un_fallo_de_github_no_se_presenta_como_exito(client, monkeypatch):
    from guardian.github import PullRequestError

    def falla(*args, **kwargs):
        raise PullRequestError("Pull Request o repositorio no encontrado.")

    monkeypatch.setattr("maas_demo.api.build_payload", falla)
    response = client.post("/api/guardian/analyze", json={"repository": "owner/repo", "pr": 99})

    assert response.status_code == 502
