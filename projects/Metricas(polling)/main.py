import logging
import json
import random
from datetime import datetime
from collections import deque
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

# Buffer en memoria para los últimos 50 eventos de trazabilidad
logs_storage = deque(maxlen=50)

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

# Endpoint de Métricas con simulación de estado para el Dashboard
@app.get("/api/metrics")
async def get_metrics():
    # Simulación aleatoria para emular salud del sistema
    db_status = "OPERATIONAL" if random.random() > 0.15 else "DEGRADED"
    
    metrics_payload = {
        "Base de Datos": {
            "status": db_status,
            "latencia": f"{random.randint(5, 45)}ms",
            "conexiones_activas": random.randint(120, 350)
        },
        "API Gateway": {
            "status": "OPERATIONAL",
            "solicitudes_por_segundo": random.randint(1200, 2500),
            "tasa_de_error": "0.01%"
        },
        "Servicio de Autenticación": {
            "status": "OPERATIONAL",
            "tiempo_respuesta": f"{random.randint(15, 60)}ms",
            "tokens_activos": random.randint(8000, 15000)
        },
        "Sistema de Pagos": {
            "status": "OPERATIONAL",
            "cola_transacciones": random.randint(0, 5),
            "exito_operaciones": "99.9%"
        }
    }

    if db_status != "OPERATIONAL":
        logger.warning("Incidencia detectada en Base de Datos", extra={
            "audit": {
                "event": "SERVICE_DEGRADED",
                "service": "Base de Datos",
                "status": db_status
            }
        })
    else:
        logger.info("Polling de métricas completado exitosamente", extra={
            "audit": {
                "event": "POLLING_METRICS",
                "status": "SUCCESS"
            }
        })

    return metrics_payload

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8028, reload=True)