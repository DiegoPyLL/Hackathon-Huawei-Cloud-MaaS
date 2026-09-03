import logging
import json
import os
import random
from datetime import datetime
from collections import deque

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

# Buffer en memoria para los últimos 50 eventos de trazabilidad
logs_storage = deque(maxlen=50)

# El estado de los servicios ya no es aleatorio: lo dicta el bus de incidentes,
# para que el semáforo, el dev-chat y el monitoreo hablen del mismo incidente.
BUS_URL = os.environ.get("BUS_URL", "http://localhost:8010")
incidentes_ya_registrados = set()


async def consultar_bus():
    """Devuelve (estado_por_panel, incidentes_activos). Si el bus no está
    levantado el panel sigue funcionando, todo en verde."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            res = await client.get(f"{BUS_URL}/api/incidentes/activos")
            res.raise_for_status()
            incidentes = res.json()["incidentes"]
    except Exception:
        return {}, []

    estado = {}
    for inc in incidentes:
        if estado.get(inc["panel_semaforo"]) != "OUTAGE":
            estado[inc["panel_semaforo"]] = inc["estado_servicio"]
    return estado, incidentes

# Formateador de logs estructurados en JSON
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        if hasattr(record, "audit"):
            log_record["audit"] = record.audit
        logs_storage.appendleft(log_record)
        return json.dumps(log_record)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("audit_logger")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

class UXLogEvent(BaseModel):
    timestamp: str
    action: str
    url: str
    userAgent: str
    details: dict = {}

# Interceptor HTTP para registrar tráfico e incidencias
@app.middleware("http")
async def log_requests(request: Request, call_next):
    if request.url.path == "/api/logs/stream":
        return await call_next(request)
        
    response = await call_next(request)
    
    is_error = response.status_code >= 400
    log_level = logger.error if is_error else logger.info
    
    audit_data = {
        "event": "HTTP_INCIDENT" if is_error else "HTTP_REQUEST",
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host,
        "status_code": response.status_code,
    }
    log_level("Petición procesada", extra={"audit": audit_data})
    return response

# Endpoint para ingesta de eventos de UX / Frontend
@app.post("/api/logs")
async def collect_frontend_logs(event: UXLogEvent, request: Request):
    is_incident = "ERROR" in event.action or "INCIDENT" in event.action
    log_func = logger.error if is_incident else logger.info
    
    log_func("Evento registrado en cliente", extra={
        "audit": {
            "event": "UX_INCIDENT" if is_incident else "UX_TRACE",
            "client_ip": request.client.host,
            "action": event.action,
            "url": event.url,
            "details": event.details
        }
    })
    return {"status": "ok"}

# Stream de logs para la SPA
@app.get("/api/logs/stream")
async def get_logs_stream():
    return list(logs_storage)

# Endpoint de Métricas con estado real tomado del bus de incidentes
@app.get("/api/metrics")
async def get_metrics():
    estado_bus, incidentes = await consultar_bus()

    metrics_payload = {
        "Base de Datos": {
            "status": estado_bus.get("Base de Datos", "OPERATIONAL"),
            "latencia": f"{random.randint(5, 45)}ms",
            "conexiones_activas": random.randint(120, 350)
        },
        "API Gateway": {
            "status": estado_bus.get("API Gateway", "OPERATIONAL"),
            "solicitudes_por_segundo": random.randint(1200, 2500),
            "tasa_de_error": "0.01%"
        },
        "Servicio de Autenticación": {
            "status": estado_bus.get("Servicio de Autenticación", "OPERATIONAL"),
            "tiempo_respuesta": f"{random.randint(15, 60)}ms",
            "tokens_activos": random.randint(8000, 15000)
        },
        "Sistema de Pagos": {
            "status": estado_bus.get("Sistema de Pagos", "OPERATIONAL"),
            "cola_transacciones": random.randint(0, 5),
            "exito_operaciones": "99.9%"
        }
    }

    # Un incidente del bus se registra una sola vez, cuando el panel lo ve por
    # primera vez. Sin esto el polling de 2s repetiría el mismo log sin parar.
    for inc in incidentes:
        if inc["incidente_id"] in incidentes_ya_registrados:
            continue
        incidentes_ya_registrados.add(inc["incidente_id"])
        logger.error("Incidencia detectada", extra={
            "audit": {
                "event": "SERVICE_DEGRADED",
                "incidente_id": inc["incidente_id"],
                "service": inc["panel_semaforo"],
                "servicio_afectado": inc["servicio"],
                "status": inc["estado_servicio"],
                "severidad": inc["severidad"],
            }
        })
        # Las líneas de alerta del incidente entran al log como evidencia real,
        # que es lo que el agente va a citar.
        for linea in inc["lineas"]:
            logger.error(linea["texto"], extra={
                "audit": {
                    "event": "INCIDENT_EVIDENCE",
                    "incidente_id": inc["incidente_id"],
                    "servicio_afectado": inc["servicio"],
                }
            })

    if not incidentes:
        logger.info("Polling de métricas completado exitosamente", extra={
            "audit": {"event": "POLLING_METRICS", "status": "SUCCESS"}
        })

    return metrics_payload

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8028, reload=True)