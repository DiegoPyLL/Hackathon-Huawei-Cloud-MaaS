#!/usr/bin/env python3
"""
Generador de tickets de email sintéticos para probar el clasificador/triage.

Cada ticket trae groundtruth (categoria_real, es_incidente, severidad_real,
prioridad_declarada) para medir precisión del agente.

La prioridad_declarada (la que pone el remitente en el sistema de tickets)
es independiente de severidad_real a propósito — prueba si el clasificador
está copiando la prioridad en vez de calcular impacto real.

Uso:
    python generate_email_tickets.py
    python generate_email_tickets.py --n 40 --seed 7 --pretty
"""

import argparse
import json
import random
from datetime import datetime, timedelta

USERS = [
    ("cliente.enterprise@bigcorp.com", "externo"),
    ("soporte@partner.com", "externo"),
    ("admin.interno@nuestra.com", "interno"),
    ("pm@nuestra.com", "interno"),
    ("account.manager@nuestra.com", "interno"),
    ("dev.lead@nuestra.com", "interno"),
    ("cto@nuestra.com", "interno"),
]

SERVICES = [
    "checkout", "auth-service", "api-gateway", "pagos", "notificaciones",
    "reportes", "bd-clientes", "batch-facturacion", "login-web",
    "app-movil", "cache-redis", "cola-mensajes",
]

CATEGORIES = {
    "indisponibilidad": {
        "weight": 0.16, "es_incidente": True,
        "severidad_pool": {"critica": 0.4, "alta": 0.4, "media": 0.2},
        "subjects": [
            "URGENTE: {service} completamente caído en producción",
            "Cliente reporta que {service} no responde",
            "Indisponibilidad total de {service}",
        ],
        "bodies": [
            "Estimado equipo, desde las {hora} el servicio {service} no responde "
            "a ninguna petición. Nuestros clientes no pueden operar. "
            "Necesitamos resolución inmediata.",
            "El servicio {service} presenta indisponibilidad total. "
            "Healthcheck en rojo. Impacto en todos los clientes de producción. "
            "Adjunto logs del error.",
        ],
    },
    "degradacion": {
        "weight": 0.12, "es_incidente": True,
        "severidad_pool": {"alta": 0.3, "media": 0.5, "baja": 0.2},
        "subjects": [
            "Latencia elevada en {service}",
            "Degradación de rendimiento en {service}",
            "{service} respondiendo muy lento",
        ],
        "bodies": [
            "Desde el mediodía el servicio {service} presenta latencia elevada "
            "(p95 sobre 3 segundos). Los timeouts están afectando a un 15%% de "
            "las transacciones.",
            "Reportamos degradación en {service}. Los tiempos de respuesta "
            "aumentaron 5x respecto a lo normal. No es caída pero afecta la "
            "experiencia de usuario.",
        ],
    },
    "error_funcional": {
        "weight": 0.14, "es_incidente": True,
        "severidad_pool": {"media": 0.5, "alta": 0.3, "baja": 0.2},
        "subjects": [
            "Bug en {service}: cálculo incorrecto",
            "Error funcional en {service}",
            "Flujo roto en {service} reportado por cliente",
        ],
        "bodies": [
            "El servicio {service} está calculando incorrectamente los descuentos. "
            "Para montos sobre $1000 el resultado es erróneo. Cliente: ACME- Corp.",
            "Se detectó un error en el flujo de {service}. El proceso se corta "
            "a mitad de camino sin mensaje de error claro. Pasos para reproducir "
            "en adjunto.",
        ],
    },
    "acceso_identidad": {
        "weight": 0.10, "es_incidente": True,
        "severidad_pool": {"alta": 0.3, "media": 0.5, "baja": 0.2},
        "subjects": [
            "Usuarios bloqueados en {service}",
            "Problema de MFA en {service}",
            "Login fallido masivo en {service}",
        ],
        "bodies": [
            "Múltiples usuarios reportan no poder iniciar sesión en {service}. "
            "El MFA rechaza códigos válidos. Ya tenemos 50+ tickets de clientes "
            "afectados.",
            "Después del reset de claves programado, varios usuarios quedaron "
            "bloqueados en {service}. Necesitamos restablecer acceso urgente.",
        ],
    },
    "datos": {
        "weight": 0.10, "es_incidente": True,
        "severidad_pool": {"alta": 0.2, "media": 0.5, "baja": 0.3},
        "subjects": [
            "Registros faltantes en {service}",
            "Datos desincronizados en {service}",
            "Integridad de datos comprometida en {service}",
        ],
        "bodies": [
            "El batch nocturno de {service} no completó. Faltan aproximadamente "
            "2000 registros del día de ayer. Puede afectar reportes ya generados.",
            "Detectamos duplicados en la tabla principal de {service}. La "
            "sincronización con el sistema origen falló silenciosamente.",
        ],
    },
    "integracion_terceros": {
        "weight": 0.10, "es_incidente": True,
        "severidad_pool": {"alta": 0.4, "media": 0.4, "baja": 0.2},
        "subjects": [
            "Pasarela de pagos rechazando transacciones",
            "Integración con {service} fallando",
            "Webhook de {service} no recibiendo eventos",
        ],
        "bodies": [
            "La pasarela de pagos está rechazando todas las transacciones con "
            "timeout. El status page del proveedor indica operativo pero no "
            "recibimos respuesta hace 30 minutos.",
            "El webhook de {service} dejó de llegar. Revisamos nuestro endpoint "
            "y está operativo. Parece problema del lado del proveedor.",
        ],
    },
    "capacidad": {
        "weight": 0.08, "es_incidente": True,
        "severidad_pool": {"alta": 0.3, "media": 0.4, "baja": 0.3},
        "subjects": [
            "Disco casi lleno en {service}",
            "Pool de conexiones agotado en {service}",
            "Rate limit excedido en {service}",
        ],
        "bodies": [
            "El disco de {service} está al 95%% de capacidad. Si no se libera "
            "espacio, el servicio dejará de funcionar en las próximas horas.",
            "Nos estamos quedando sin conexiones en el pool de {service}. "
            "El rate limit está saltando constantemente y bloqueando peticiones.",
        ],
    },
    "seguridad": {
        "weight": 0.06, "es_incidente": True,
        "severidad_pool": {"critica": 0.3, "alta": 0.5, "media": 0.2},
        "subjects": [
            "ALERTA DE SEGURIDAD: actividad sospechosa en {service}",
            "Credencial expuesta detectada",
            "Reporte de phishing suplantando {service}",
        ],
        "bodies": [
            "Detectamos intentos de login desde IPs no reconocidas en {service}. "
            "Patrón de fuerza bruta sobre cuentas administrativas. Bloqueo "
            "preventivo recomendado.",
            "Se detectó una credencial de {service} expuesta en un repositorio "
            "público. Es necesario rotar claves inmediatamente y revisar accesos.",
        ],
    },
    "solicitud": {
        "weight": 0.09, "es_incidente": False,
        "severidad_pool": {},
        "subjects": [
            "Consulta sobre configuración de {service}",
            "Solicitud de acceso a {service}",
            "Cómo configurar integración con {service}",
        ],
        "bodies": [
            "Buen día, necesitamos documentación sobre cómo configurar la "
            "integración con {service} desde nuestro lado. ¿Tienen un SDK "
            "disponible?",
            "Solicito acceso al panel de administración de {service} para el "
            "equipo de QA. ¿Cuál es el proceso?",
        ],
    },
    "ruido": {
        "weight": 0.05, "es_incidente": False,
        "severidad_pool": {},
        "subjects": [
            "Confirmación de resolución de {service}",
            "Agradecimiento por soporte",
            "Cierre de ticket - {service}",
        ],
        "bodies": [
            "Confirmamos que el servicio {service} volvió a la normalidad. "
            "Gracias por la rápida resolución. Pueden cerrar el ticket.",
            "Muchas gracias por la ayuda con {service}, todo funcionando "
            "correctamente ahora.",
        ],
    },
}

PRIORIDAD_POOL = {"P1": 0.15, "P2": 0.35, "P3": 0.35, "P4": 0.15}


def weighted_choice(pool: dict):
    items, weights = zip(*pool.items())
    return random.choices(items, weights=weights, k=1)[0]


def random_timestamp(days_back=90):
    now = datetime.now()
    delta_days = random.randint(0, days_back)
    hour = random.randint(7, 23)
    minute = random.randint(0, 59)
    ts = now - timedelta(days=delta_days)
    return ts.replace(hour=hour, minute=minute, second=0, microsecond=0)


def build_ticket(idx, category):
    cfg = CATEGORIES[category]
    servicio = random.choice(SERVICES)
    remitente = random.choice(USERS)
    t0 = random_timestamp()
    ctx = {"service": servicio, "hora": t0.strftime("%H:%M")}

    subject = random.choice(cfg["subjects"]).format(**ctx)
    body = random.choice(cfg["bodies"]).format(**ctx)

    severidad = weighted_choice(cfg["severidad_pool"]) if cfg["es_incidente"] else "n/a"
    prioridad = weighted_choice(PRIORIDAD_POOL)

    return {
        "ticket_id": f"EMAIL-{idx:04d}",
        "categoria_real": category,
        "es_incidente": cfg["es_incidente"],
        "severidad_real": severidad,
        "prioridad_declarada": prioridad,
        "servicio_afectado": servicio if cfg["es_incidente"] else None,
        "remitente": remitente[0],
        "tipo_remitente": remitente[1],
        "subject": subject,
        "body": body,
        "timestamp": t0.isoformat(),
    }


def main():
    ap = argparse.ArgumentParser(description="Generador de tickets de email sintéticos")
    ap.add_argument("--n", type=int, default=40, help="cantidad de tickets a generar")
    ap.add_argument("--seed", type=int, default=None, help="semilla para reproducibilidad")
    ap.add_argument("--out", type=str, default="../data/email_tickets.jsonl")
    ap.add_argument("--pretty", action="store_true", help="imprime los primeros 3 tickets en consola")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    categorias = list(CATEGORIES.keys())
    pesos = [CATEGORIES[c]["weight"] for c in categorias]

    tickets = []
    for i in range(1, args.n + 1):
        cat = random.choices(categorias, weights=pesos, k=1)[0]
        tickets.append(build_ticket(i, cat))

    with open(args.out, "w", encoding="utf-8") as f:
        for t in tickets:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    conteo = {}
    for t in tickets:
        conteo[t["categoria_real"]] = conteo.get(t["categoria_real"], 0) + 1

    print(f"Generados {len(tickets)} tickets -> {args.out}")
    print("Distribución por categoría:")
    for c, n in sorted(conteo.items(), key=lambda x: -x[1]):
        print(f"  {c:22s} {n}")

    if args.pretty:
        print("\n--- muestra ---")
        for t in tickets[:3]:
            print(f"\n[{t['ticket_id']}] {t['categoria_real']} | "
                  f"incidente={t['es_incidente']} | severidad={t['severidad_real']} | "
                  f"prioridad={t['prioridad_declarada']}")
            print(f"  Subject: {t['subject']}")
            print(f"  Body: {t['body'][:100]}...")


if __name__ == "__main__":
    main()
