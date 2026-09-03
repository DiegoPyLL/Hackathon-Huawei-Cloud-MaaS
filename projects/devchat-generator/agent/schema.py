"""
Schema canónico de incidente.

Un incidente es un incidente independientemente del canal por donde entró.
El clasificador produce siempre esta estructura, venga de email, monitoring
o dev chat.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Canal(str, enum.Enum):
    email = "email"
    monitoring = "monitoring"
    devchat = "devchat"


class Categoria(str, enum.Enum):
    indisponibilidad = "indisponibilidad"
    degradacion = "degradacion"
    error_funcional = "error_funcional"
    acceso_identidad = "acceso_identidad"
    datos = "datos"
    integracion_terceros = "integracion_terceros"
    capacidad = "capacidad"
    seguridad = "seguridad"
    solicitud = "solicitud"
    ruido = "ruido"


class Severidad(str, enum.Enum):
    critica = "critica"
    alta = "alta"
    media = "media"
    baja = "baja"
    n_a = "n/a"


CATEGORIAS_INCIDENTE = {
    Categoria.indisponibilidad,
    Categoria.degradacion,
    Categoria.error_funcional,
    Categoria.acceso_identidad,
    Categoria.datos,
    Categoria.integracion_terceros,
    Categoria.capacidad,
    Categoria.seguridad,
}


class SenalEntrante(BaseModel):
    """Señal cruda que entra por cualquier canal, antes de clasificar."""

    canal: Canal
    id_externo: str = Field(description="ID en el sistema origen (thread_id, message_id, alert_id, ticket_id)")
    timestamp: datetime
    servicio_afectado: str | None = None
    texto: str = Field(description="Contenido concatenado o cuerpo principal")
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncidentePrevioRef(BaseModel):
    """Referencia a un incidente previo encontrado por RAG."""

    id: str
    resumen: str
    causa_raiz: str
    solucion: str
    fecha: str
    score: float = Field(description="Similitud [0,1]")


class IncidenteConsolidado(BaseModel):
    """Salida canónica del agente de triage."""

    id: str = Field(description="ID asignado por el agente (INC-AGENT-XXXX)")
    canal_origen: Canal
    id_externo: str
    categoria: Categoria
    es_incidente: bool
    severidad: Severidad
    servicio_afectado: str | None = None
    resumen: str = Field(description="Resumen ejecutivo 1-2 frases")
    causa_raiz_probable: str | None = None
    acciones_recomendadas: list[str] = Field(default_factory=list)
    incidentes_previos_similares: list[IncidentePrevioRef] = Field(default_factory=list)
    dueño_sugerido: str | None = None
    duplicado_de: str | None = Field(default=None, description="ID de otro incidente si este es duplicado")
    confianza: float = Field(ge=0.0, le=1.0)
    requiere_revision: bool = Field(
        default=False,
        description="El clasificador devolvió algo que no valida contra la taxonomía",
    )
    motivo_revision: str | None = None
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    def es_incidente_real(self) -> bool:
        return self.es_incidente and self.categoria in CATEGORIAS_INCIDENTE


DUEÑOS_POR_ROL = {
    Categoria.indisponibilidad: "sre-oncall",
    Categoria.degradacion: "sre-oncall",
    Categoria.error_funcional: "tech-lead-backend",
    Categoria.acceso_identidad: "sre-oncall",
    Categoria.datos: "data-eng",
    Categoria.integracion_terceros: "tech-lead-backend",
    Categoria.capacidad: "sre-oncall",
    Categoria.seguridad: "security-team",
    Categoria.solicitud: None,
    Categoria.ruido: None,
}


def dueño_sugerido(categoria: Categoria) -> str | None:
    return DUEÑOS_POR_ROL.get(categoria)
