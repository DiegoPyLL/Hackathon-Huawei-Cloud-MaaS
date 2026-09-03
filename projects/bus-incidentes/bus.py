#!/usr/bin/env python3
"""
Bus de incidentes — fuente de verdad compartida por todos los canales.

El problema que resuelve: cada sistema (dev-chat, monitoreo, semaforo/logs,
email) generaba sus propios incidentes al azar, sin relacion entre si. Asi el
agente no puede correlacionar nada, porque no hay nada que correlacionar: son
cuatro streams de ruido independiente.

Aca un mismo incidente real se emite una sola vez y cada canal lo renderiza en
su propio formato:

    escenario canonico (projects/monitoreo)
             |
             v
      INCIDENTE VIVO  (INC-xx, tipo, severidad, servicio, accion esperada)
             |
    +--------+--------+------------------+
    v        v        v                  v
 monitoreo  dev-chat  semaforo+logs     email
 (lineas)   (hilo)    (servicio rojo)   (ticket)

Reusa los 16 escenarios de `projects/monitoreo/generator/` — no duplica la
taxonomia ni el catalogo de acciones, los importa.

Uso:
    uvicorn bus:app --port 8010
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent
MONITOREO_GEN = BASE_DIR.parent / "monitoreo" / "generator"
sys.path.insert(0, str(MONITOREO_GEN))

from generate_monitoreo_dumps import (  # noqa: E402
    ESCENARIOS,
    RUTEO_DEFECTO,
    SERVICIOS,
    Ids,
)

# Cada cuanto nace un incidente nuevo, en segundos.
INTERVALO_INCIDENTE = (75.0, 150.0)
# Cuanto vive un incidente antes de darse por resuelto.
DURACION_INCIDENTE_MIN = (3, 6)
MAX_INCIDENTES_ACTIVOS = 3

# El semaforo del dashboard tiene 4 paneles; los servicios del escenario son 14.
# Este mapa traduce de uno al otro para que el panel correcto se ponga en rojo.
SERVICIO_A_PANEL = {
    "bd-clientes": "Base de Datos",
    "cache-redis": "Base de Datos",
    "batch-facturacion": "Base de Datos",
    "reportes": "Base de Datos",
    "api-gateway": "API Gateway",
    "checkout": "API Gateway",
    "buscar": "API Gateway",
    "pedidos": "API Gateway",
    "notificaciones": "API Gateway",
    "cola-mensajes": "API Gateway",
    "auth-service": "Servicio de Autenticación",
    "login-web": "Servicio de Autenticación",
    "pagos": "Sistema de Pagos",
    "app-movil": "Sistema de Pagos",
}

# El tipo manda sobre el servicio al elegir panel: un incidente de datos enciende
# "Base de Datos" aunque el servicio que lo expone sea el gateway.
PANEL_POR_TIPO = {
    "datos": "Base de Datos",
    "acceso-identidad": "Servicio de Autenticación",
    "seguridad": "Servicio de Autenticación",
}

SEVERIDAD_A_ESTADO = {
    "critica": "OUTAGE",
    "alta": "OUTAGE",
    "media": "DEGRADED",
    "baja": "DEGRADED",
}


# Si las lineas no nombran ningun servicio, el tipo decide donde duele.
SERVICIO_POR_TIPO = {
    "datos": "bd-clientes",
    "acceso-identidad": "auth-service",
    "seguridad": "auth-service",
    "integracion-terceros": "pagos",
    "capacidad": "bd-clientes",
}


def servicio_del_escenario(esc: dict) -> str:
    """El escenario no declara el servicio como campo; lo menciona dentro de las
    lineas. Se busca el primero que aparezca, con el tipo como respaldo."""
    texto = " ".join(linea for _, linea in esc["lines"]) + " " + esc["slug"]
    for servicio in sorted(SERVICIOS, key=len, reverse=True):
        if servicio in texto:
            return servicio
    return SERVICIO_POR_TIPO.get(esc["tipo"], "api-gateway")


class Incidente:
    def __init__(self, numero: int, slug_escenario: str, esc: dict):
        self.incidente_id = f"INC-{numero:02d}"
        self.escenario = slug_escenario
        self.slug = esc["slug"]
        self.tipo = esc["tipo"]
        self.severidad = esc["severidad"]
        self.especialistas = esc["especialistas"]
        self.ataque_activo = esc["ataque_activo"]
        self.accion_esperada = esc.get("accion")
        self.nota = esc.get("nota", "")
        self.servicio = servicio_del_escenario(esc)
        self.panel = PANEL_POR_TIPO.get(self.tipo) or SERVICIO_A_PANEL.get(self.servicio, "API Gateway")
        self.estado_servicio = SEVERIDAD_A_ESTADO[self.severidad]

        self.inicio = datetime.now()
        self.fin = self.inicio + timedelta(minutes=random.randint(*DURACION_INCIDENTE_MIN))
        self.resuelto = False

        # Las lineas del escenario traen offsets en segundos respecto a t0
        # (algunos negativos: son precursores anteriores a la alerta).
        self.lineas = [
            {
                "offset_seg": offset,
                "timestamp": (self.inicio + timedelta(seconds=offset)).isoformat(timespec="seconds"),
                "texto": texto,
            }
            for offset, texto in sorted(esc["lines"], key=lambda x: x[0])
        ]

        # Que canales ya lo reportaron. Cada canal se marca solo al hacerlo, y
        # a proposito no todos reportan todo: esa asimetria es la que obliga al
        # agente a correlacionar de verdad.
        self.reportado_en = {}

    def marcar_reportado(self, canal: str):
        self.reportado_en[canal] = datetime.now().isoformat(timespec="seconds")

    def as_dict(self) -> dict:
        return {
            "incidente_id": self.incidente_id,
            "escenario": self.escenario,
            "slug": self.slug,
            "tipo": self.tipo,
            "severidad": self.severidad,
            "servicio": self.servicio,
            "panel_semaforo": self.panel,
            "estado_servicio": self.estado_servicio,
            "especialistas": self.especialistas,
            "ruteo_defecto": RUTEO_DEFECTO.get(self.tipo),
            "ataque_activo": self.ataque_activo,
            "accion_esperada": self.accion_esperada,
            "nota": self.nota,
            "inicio": self.inicio.isoformat(timespec="seconds"),
            "resuelto": self.resuelto,
            "reportado_en": self.reportado_en,
            "lineas": self.lineas,
        }


class BusIncidentes:
    def __init__(self):
        self.incidentes: list[Incidente] = []
        self._contador = 0
        self._task: asyncio.Task | None = None
        self.rng = random.Random()

    @property
    def activos(self) -> list[Incidente]:
        return [i for i in self.incidentes if not i.resuelto]

    def crear(self, escenario: str | None = None) -> Incidente:
        if escenario is None:
            escenario = self.rng.choice(list(ESCENARIOS.keys()))
        if escenario not in ESCENARIOS:
            raise KeyError(escenario)

        esc = ESCENARIOS[escenario](Ids(self.rng), self.rng)
        self._contador += 1
        incidente = Incidente(self._contador, escenario, esc)
        self.incidentes.append(incidente)
        print(f"[bus] nace {incidente.incidente_id} {incidente.tipo} "
              f"servicio={incidente.servicio} sev={incidente.severidad}", flush=True)
        return incidente

    def estado_servicios(self) -> dict:
        """Estado por panel del semaforo. Si dos incidentes pegan al mismo panel
        gana el peor."""
        estado = {}
        for inc in self.activos:
            actual = estado.get(inc.panel)
            if actual == "OUTAGE":
                continue
            estado[inc.panel] = inc.estado_servicio
        return estado

    def _cerrar_vencidos(self):
        ahora = datetime.now()
        for inc in self.activos:
            if ahora >= inc.fin:
                inc.resuelto = True
                print(f"[bus] resuelto {inc.incidente_id}", flush=True)

    async def run(self):
        while True:
            await asyncio.sleep(self.rng.uniform(*INTERVALO_INCIDENTE))
            self._cerrar_vencidos()
            if len(self.activos) < MAX_INCIDENTES_ACTIVOS:
                self.crear()

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self.run())


bus = BusIncidentes()
app = FastAPI(title="Bus de incidentes")

# Los canales corren en puertos distintos y algunos consultan desde el navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    bus.crear()  # que la demo arranque con algo vivo, sin esperar el primer ciclo
    bus.start()
    print("[bus] escuchando; escenarios disponibles:", len(ESCENARIOS), flush=True)


@app.get("/api/incidentes/activos")
async def incidentes_activos():
    bus._cerrar_vencidos()
    return {"incidentes": [i.as_dict() for i in bus.activos]}


@app.get("/api/incidentes")
async def todos_los_incidentes():
    return {"incidentes": [i.as_dict() for i in bus.incidentes]}


@app.get("/api/estado-servicios")
async def estado_servicios():
    bus._cerrar_vencidos()
    return {"servicios": bus.estado_servicios()}


@app.get("/api/feed/monitoreo")
async def feed_monitoreo():
    """Las lineas de alerta de los incidentes vivos, en el formato de volcado que
    espera el Orquestador (fase 1)."""
    bus._cerrar_vencidos()
    lineas = []
    for inc in bus.activos:
        for linea in inc.lineas:
            lineas.append(f"MONITOREO {linea['timestamp'][11:19]} {linea['texto']}")
        inc.marcar_reportado("monitoreo")
    return {"volcado": " | ".join(lineas), "lineas": lineas}


@app.post("/api/incidentes/provocar")
async def provocar(payload: dict | None = None):
    """Disparo manual — el boton de la demo."""
    escenario = (payload or {}).get("escenario")
    try:
        incidente = bus.crear(escenario)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"escenario desconocido: {escenario}")
    return incidente.as_dict()


@app.post("/api/incidentes/{incidente_id}/reportado")
async def marcar_reportado(incidente_id: str, payload: dict):
    """Un canal avisa que ya reporto este incidente a su manera."""
    canal = payload.get("canal")
    for inc in bus.incidentes:
        if inc.incidente_id == incidente_id:
            inc.marcar_reportado(canal)
            return {"ok": True, "reportado_en": inc.reportado_en}
    raise HTTPException(status_code=404, detail=incidente_id)


@app.get("/api/escenarios")
async def escenarios():
    return {"escenarios": sorted(ESCENARIOS.keys())}


@app.get("/api/verdad")
async def verdad():
    """Groundtruth para puntuar al agente: que paso de verdad y por que canales
    se reporto cada cosa."""
    incidentes = [i.as_dict() for i in bus.incidentes]
    por_tipo = {}
    for inc in incidentes:
        por_tipo[inc["tipo"]] = por_tipo.get(inc["tipo"], 0) + 1
    return {
        "total_incidentes": len(incidentes),
        "activos": len(bus.activos),
        "por_tipo": por_tipo,
        "incidentes": incidentes,
    }
