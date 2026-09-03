"""Cliente de Supabase vía PostgREST, sin dependencias de runtime.

El [ADR-0005](../../docs/architecture/decisions/0005-supabase-como-almacen.md)
eligió PostgREST sobre HTTPS y no un driver de Postgres, para conservar la
ausencia de dependencias. Este módulo sigue el patrón de `provider.py`: el
`opener` es inyectable, de modo que el camino completo se puede probar sin red
ni base de datos.

La `service_role` ignora las políticas RLS: solo vive en el backend y jamás
aparece en un mensaje de error, en un log ni en el navegador.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any


# Tablas declaradas en projects/incident-agent/schema/schema_incidentes.sql
TABLAS = ("incidentes", "incidente_eventos", "emails_entrantes", "emails_salientes")


class AlmacenError(RuntimeError):
    """El almacén no pudo completar la operación."""


class Almacen:
    """Acceso de lectura y escritura a las tablas del incidente."""

    def __init__(
        self,
        *,
        url: str,
        service_key: str,
        timeout_seconds: float = 15.0,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        if not url:
            raise AlmacenError("Falta SUPABASE_URL.")
        if not service_key:
            raise AlmacenError("Falta SUPABASE_SERVICE_ROLE_KEY.")
        self.base_url = url.rstrip("/")
        self.service_key = service_key
        self.timeout_seconds = timeout_seconds
        self.opener = opener

    @classmethod
    def desde_entorno(cls, **kwargs: Any) -> Almacen:
        """Construye el almacén desde el entorno. Falla declarando qué falta."""
        return cls(
            url=os.environ.get("SUPABASE_URL", ""),
            service_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
            **kwargs,
        )

    @property
    def rest_url(self) -> str:
        suffix = "/rest/v1"
        return self.base_url if self.base_url.endswith(suffix) else self.base_url + suffix

    def _pedir(self, metodo: str, ruta: str, *, cuerpo: Any = None, cabeceras: dict | None = None) -> Any:
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        request = urllib.request.Request(
            f"{self.rest_url}{ruta}",
            data=datos,
            headers={
                "apikey": self.service_key,
                "Authorization": f"Bearer {self.service_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                **(cabeceras or {}),
            },
            method=metodo,
        )
        try:
            with self.opener(request, timeout=self.timeout_seconds) as respuesta:
                crudo = respuesta.read()
        except urllib.error.HTTPError as error:
            raise AlmacenError(_explicar(error.code, metodo, ruta)) from error
        except urllib.error.URLError as error:
            raise AlmacenError("No se pudo conectar con Supabase.") from error
        except TimeoutError as error:
            raise AlmacenError("Supabase superó el tiempo de espera.") from error

        if not crudo:
            return []
        try:
            return json.loads(crudo)
        except json.JSONDecodeError as error:
            raise AlmacenError("Supabase devolvió una respuesta que no es JSON.") from error

    def verificar(self) -> dict[str, Any]:
        """Comprueba credencial y alcance. Devuelve el conteo por tabla."""
        conteos: dict[str, Any] = {}
        for tabla in TABLAS:
            try:
                conteos[tabla] = self.contar(tabla)
            except AlmacenError as error:
                conteos[tabla] = f"error: {error}"
        return conteos

    def contar(self, tabla: str) -> int:
        """Número de filas, pidiendo solo la cabecera Content-Range."""
        request = urllib.request.Request(
            f"{self.rest_url}/{tabla}?select=*",
            headers={
                "apikey": self.service_key,
                "Authorization": f"Bearer {self.service_key}",
                "Range": "0-0",
                "Prefer": "count=exact",
            },
            method="GET",
        )
        try:
            with self.opener(request, timeout=self.timeout_seconds) as respuesta:
                rango = respuesta.headers.get("Content-Range", "")
        except urllib.error.HTTPError as error:
            raise AlmacenError(_explicar(error.code, "GET", f"/{tabla}")) from error
        except urllib.error.URLError as error:
            raise AlmacenError("No se pudo conectar con Supabase.") from error
        # Content-Range llega como "0-0/12" o "*/0"
        total = rango.rsplit("/", 1)[-1] if "/" in rango else ""
        return int(total) if total.isdigit() else 0

    def consultar(self, tabla: str, *, limite: int = 20, orden: str | None = None) -> list[dict]:
        ruta = f"/{tabla}?select=*&limit={int(limite)}"
        if orden:
            ruta += f"&order={urllib.parse.quote(orden, safe='.')}"
        filas = self._pedir("GET", ruta)
        return filas if isinstance(filas, list) else [filas]

    def insertar(self, tabla: str, fila: dict) -> list[dict]:
        filas = self._pedir(
            "POST", f"/{tabla}", cuerpo=fila, cabeceras={"Prefer": "return=representation"}
        )
        return filas if isinstance(filas, list) else [filas]


def _explicar(codigo: int, metodo: str, ruta: str) -> str:
    """Traduce el código HTTP sin citar jamás la credencial."""
    conocidos = {
        401: "Supabase rechazó la credencial (401). Revisa SUPABASE_SERVICE_ROLE_KEY.",
        403: "La credencial no tiene permiso sobre ese recurso (403).",
        404: f"La tabla o ruta no existe en Supabase (404): {ruta}.",
    }
    if codigo in conocidos:
        return conocidos[codigo]
    if 500 <= codigo < 600:
        return f"Supabase respondió con un error del servidor ({codigo})."
    return f"Supabase rechazó {metodo} {ruta} con HTTP {codigo}."
