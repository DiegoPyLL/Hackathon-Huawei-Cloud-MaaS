"""Servidor HTTP del vertical slice, basado solo en la biblioteca estándar."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .config import Config
from .provider import ProviderError, build_provider
from .service import ChatService, ValidationError


STATIC_DIR = Path(__file__).with_name("static")
MAX_REQUEST_BYTES = 64 * 1024
STATIC_ROUTES = {
    "/": "index.html",
    "/app.js": "app.js",
    "/styles.css": "styles.css",
}


def create_handler(config: Config):
    service = ChatService(build_provider(config))

    class AppHandler(BaseHTTPRequestHandler):
        server_version = "MaaSVerticalSlice/1.0"

        def do_GET(self) -> None:
            if self.path == "/api/health":
                self._json(
                    HTTPStatus.OK,
                    {"status": "ok", "mode": config.mode, "model": config.model},
                )
                return
            filename = STATIC_ROUTES.get(self.path)
            if filename is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Ruta no encontrada."})
                return
            self._static(filename)

        def do_POST(self) -> None:
            if self.path != "/api/chat/stream":
                self._json(HTTPStatus.NOT_FOUND, {"error": "Ruta no encontrada."})
                return
            try:
                payload = self._read_json()
                stream = service.stream(payload.get("messages"))
            except (ValidationError, ValueError) as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self._security_headers()
            self.end_headers()
            try:
                for event in stream:
                    self._sse(event)
            except (ProviderError, OSError) as error:
                self._sse({"type": "error", "error": str(error)})
            self.close_connection = True

        def _read_json(self) -> dict[str, Any]:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("Falta Content-Length.")
            try:
                length = int(raw_length)
            except ValueError as error:
                raise ValueError("Content-Length inválido.") from error
            if not 0 < length <= MAX_REQUEST_BYTES:
                raise ValueError("La petición está vacía o supera 64 KiB.")
            try:
                payload = json.loads(self.rfile.read(length))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("El cuerpo debe ser JSON válido.") from error
            if not isinstance(payload, dict):
                raise ValueError("El cuerpo JSON debe ser un objeto.")
            return payload

        def _static(self, filename: str) -> None:
            content = (STATIC_DIR / filename).read_bytes()
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self._security_headers()
            self.end_headers()
            self.wfile.write(content)

        def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self._security_headers()
            self.end_headers()
            self.wfile.write(content)

        def _sse(self, event: dict[str, Any]) -> None:
            content = f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")
            self.wfile.write(content)
            self.wfile.flush()

        def _security_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; connect-src 'self'; "
                "script-src 'self'; style-src 'self'; img-src 'self' data:",
            )

        def log_message(self, format: str, *args: object) -> None:
            print(f"http {self.address_string()} {format % args}")

    return AppHandler


def create_server(
    config: Config, *, host: str = "127.0.0.1", port: int = 8000
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), create_handler(config))
