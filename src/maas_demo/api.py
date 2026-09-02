"""Aplicación FastAPI: chat del vertical slice y AI Cloud Deployment Guardian."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from guardian import patch, policy, publish
from guardian.analyzer import analyze_payload
from guardian.github import PullRequestError, build_payload

from .config import Config
from .provider import ProviderError, build_provider
from .service import ChatService, ValidationError


STATIC_DIR = Path(__file__).with_name("static")
MAX_REQUEST_BYTES = 64 * 1024
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; connect-src 'self'; "
        "script-src 'self'; style-src 'self'; img-src 'self' data:"
    ),
}


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


class AnalyzeRequest(BaseModel):
    repository: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")
    pr: int = Field(ge=1)
    environment: str = policy.DEFAULT_ENVIRONMENT
    publish: bool = True


class PatchRequest(BaseModel):
    repository: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")
    pr: int = Field(ge=1)
    environment: str = policy.DEFAULT_ENVIRONMENT


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config.from_env()
    provider = build_provider(config)
    chat = ChatService(provider)

    app = FastAPI(title="AI Cloud Deployment Guardian", docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and int(length) > MAX_REQUEST_BYTES:
            return JSONResponse({"error": "La petición supera 64 KiB."}, status_code=413)

        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": config.mode, "model": config.model}

    @app.post("/api/chat/stream")
    def chat_stream(body: ChatRequest) -> StreamingResponse:
        try:
            stream = chat.stream([message.model_dump() for message in body.messages])
        except ValidationError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        def events():
            try:
                for event in stream:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except (ProviderError, OSError) as error:
                payload = json.dumps({"type": "error", "error": str(error)})
                yield f"data: {payload}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/api/guardian/analyze")
    def analyze(body: AnalyzeRequest) -> dict[str, Any]:
        return _run_analysis(body, config, provider, publish_result=body.publish)[1]

    @app.post("/api/guardian/patch")
    def generate_patch(body: PatchRequest) -> dict[str, Any]:
        # El parche no vuelve a publicar: el veredicto ya está en el Pull Request.
        payload, report = _run_analysis(body, config, provider, publish_result=False)
        return patch.generate(
            report["findings"], payload["files"], provider=provider, mode=config.mode
        )

    for route, filename in {"/": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}.items():
        app.get(route, include_in_schema=False)(_static_route(filename))

    return app


def _run_analysis(
    body: Any, config: Config, provider: Any, *, publish_result: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Descarga el Pull Request y lo analiza. Devuelve (payload, informe)."""
    token = os.getenv("GITHUB_TOKEN")
    try:
        payload = build_payload(body.repository, body.pr, token=token)
        report = analyze_payload(
            payload,
            provider=provider,
            mode=config.mode,
            environment=body.environment,
            token=token,
        )
        if publish_result:
            report["publication"] = publish.publish(report, body.pr, token)
    except policy.PolicyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except PullRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ProviderError as error:
        # Un fallo live nunca se presenta como éxito mock.
        raise HTTPException(status_code=502, detail=str(error)) from error
    return payload, report


def _static_route(filename: str):
    def serve() -> FileResponse:
        return FileResponse(STATIC_DIR / filename, headers={"Cache-Control": "no-cache"})

    return serve


app = create_app()
