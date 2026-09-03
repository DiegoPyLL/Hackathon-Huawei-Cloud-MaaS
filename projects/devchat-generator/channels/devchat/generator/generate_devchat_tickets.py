#!/usr/bin/env python3
"""
Generador de hilos sintéticos de dev chat (estilo Slack) para probar
un clasificador/triage de incidentes.

Cada hilo trae groundtruth (categoria_real, es_incidente, severidad_real, etc.)
para que puedas medir precisión del agente sin depender de etiquetado manual.

Uso:
    python generate_devchat_tickets.py
    python generate_devchat_tickets.py --n 60 --seed 7 --pretty
"""

import argparse
import json
import random
from datetime import datetime, timedelta

# --------------------------------------------------------------------------
# Vocabulario base
# --------------------------------------------------------------------------

USERS = [
    ("bpereira", "dev"),
    ("camila.rios", "dev"),
    ("nano_sre", "sre"),
    ("fely.ops", "sre"),
    ("jcontreras", "dev"),
    ("root_marce", "sre"),
    ("pao_qa", "qa"),
    ("diego.lead", "lead"),
    ("valen_pm", "pm"),
    ("seba_infra", "sre"),
]

SERVICES = [
    "checkout", "auth-service", "api-gateway", "pagos", "notificaciones",
    "reportes", "bd-clientes", "batch-facturacion", "login-web",
    "app-movil", "cache-redis", "cola-mensajes",
]

CHANNELS = ["#incidentes", "#on-call", "#dev-backend", "#alerts-prod", "#general-dev"]

# --------------------------------------------------------------------------
# Categorías: taxonomía canónica (8 tipos de incidente + solicitud + ruido)
# --------------------------------------------------------------------------

CATEGORIES = {
    "indisponibilidad": {
        "weight": 0.14, "es_incidente": True,
        "severidad_pool": {"critica": 0.4, "alta": 0.4, "media": 0.2},
        "openers": [
            "🚨 {service} está caído, nadie puede hacer login",
            "oye {service} tira 502 en todos los requests, alguien más?",
            "{service} no responde desde hace como 10 min",
        ],
        "followups": [
            "confirmado, healthcheck en rojo desde las {hora}",
            "lo mismo en staging o solo prod?",
            "pod de {service} en crashloop, viendo logs",
            "clientes ya están reclamando por redes sociales",
        ],
        "resolutions": [
            "se reinició el pod y volvió, quedamos atentos",
            "era un deploy mal aplicado, se hizo rollback y ya volvió",
        ],
    },
    "degradacion": {
        "weight": 0.12, "es_incidente": True,
        "severidad_pool": {"alta": 0.3, "media": 0.5, "baja": 0.2},
        "openers": [
            "{service} está lentísimo, p95 se fue a las nubes",
            "latencia de {service} subió como 5x desde el mediodía",
            "usuarios reportando que tarda una eternidad en cargar",
        ],
        "followups": [
            "cpu del {service} al 90%, parece cuello de botella",
            "puede ser el redis, está con más misses que de costumbre",
            "cuántos usuarios afectados aprox?",
        ],
        "resolutions": [
            "se escaló el número de réplicas y bajó la latencia",
            "encontramos una query sin índice, se optimizó",
        ],
    },
    "error_funcional": {
        "weight": 0.14, "es_incidente": True,
        "severidad_pool": {"media": 0.5, "alta": 0.3, "baja": 0.2},
        "openers": [
            "el cálculo de {service} está dando resultados raros",
            "encontré un bug en {service}, el descuento no se aplica bien",
            "{user2} reportó que el flujo de {service} se corta a mitad de camino",
        ],
        "followups": [
            "puedes mandar un ejemplo con el id del caso?",
            "reproduje en staging, es el mismo comportamiento",
            "esto viene del último deploy o es viejo?",
        ],
        "resolutions": [
            "era un edge case con montos negativos, el fix ya está en review",
            "se corrigió la validación y se desplegó a prod",
        ],
    },
    "acceso_identidad": {
        "weight": 0.10, "es_incidente": True,
        "severidad_pool": {"alta": 0.3, "media": 0.5, "baja": 0.2},
        "openers": [
            "varios usuarios no pueden loguearse en {service}",
            "el MFA de {service} está rechazando códigos válidos",
            "tengo tickets de gente bloqueada después del reset de clave",
        ],
        "followups": [
            "es general o algún segmento en particular?",
            "parece que el token expira antes de tiempo",
            "cuántos casos llevas registrados?",
        ],
        "resolutions": [
            "era un desfase de reloj en el servidor de auth, se corrigió",
            "se restableció el acceso manualmente a los afectados",
        ],
    },
    "datos": {
        "weight": 0.10, "es_incidente": True,
        "severidad_pool": {"alta": 0.2, "media": 0.5, "baja": 0.3},
        "openers": [
            "faltan registros en {service}, el batch de anoche no corrió completo",
            "los datos de {service} están desincronizados con el origen",
            "{user2} dice que hay duplicados en la tabla de {service}",
        ],
        "followups": [
            "reviso el job de sync, parece que falló silenciosamente",
            "cuántos registros están afectados?",
            "esto puede haber llegado a reportes ya generados",
        ],
        "resolutions": [
            "se re-ejecutó el batch y se reconciliaron los datos",
            "era un problema de encoding en la carga, se corrigió el importador",
        ],
    },
    "integracion_terceros": {
        "weight": 0.10, "es_incidente": True,
        "severidad_pool": {"alta": 0.4, "media": 0.4, "baja": 0.2},
        "openers": [
            "la pasarela de pagos está rechazando todo con timeout",
            "el proveedor de {service} está devolviendo 500 hace rato",
            "webhook de {service} dejó de llegar",
        ],
        "followups": [
            "revisé el status page del proveedor, dice operativo, raro",
            "puede ser rate limit de nuestro lado",
            "abrí ticket con el proveedor, esperando respuesta",
        ],
        "resolutions": [
            "el proveedor confirmó incidente de su parte, ya se restableció",
            "se activó el circuito de retry y se normalizó",
        ],
    },
    "capacidad": {
        "weight": 0.08, "es_incidente": True,
        "severidad_pool": {"alta": 0.3, "media": 0.4, "baja": 0.3},
        "openers": [
            "disco de {service} al 95%, esto va a explotar",
            "nos estamos quedando sin conexiones en el pool de {service}",
            "rate limit de {service} saltando constantemente",
        ],
        "followups": [
            "cuánto nos queda antes de que colapse?",
            "hay algo generando logs de más de lo normal?",
        ],
        "resolutions": [
            "se limpió espacio y se subió la cuota, monitoreando",
            "se aumentó el pool de conexiones",
        ],
    },
    "seguridad": {
        "weight": 0.06, "es_incidente": True,
        "severidad_pool": {"critica": 0.3, "alta": 0.5, "media": 0.2},
        "openers": [
            "🚨 detecté intentos de login raros desde IPs que no son de acá",
            "parece que se filtró una credencial de {service} en un repo",
            "alguien reporta un correo de phishing suplantando a soporte",
        ],
        "followups": [
            "ya se rotaron las credenciales?",
            "bloqueamos esas IPs mientras se investiga",
        ],
        "resolutions": [
            "se rotaron las claves y se revisó que no hubo acceso indebido",
            "se bloqueó el dominio del phishing y se avisó a los usuarios",
        ],
    },
    "solicitud": {
        "weight": 0.09, "es_incidente": False,
        "severidad_pool": {},
        "openers": [
            "alguien sabe cómo se configura el ambiente de {service} en local?",
            "necesito acceso al repo de {service}, quién lo administra",
            "podemos agendar para revisar el diseño de {service}?",
        ],
        "followups": [
            "yo tengo la doc, te la paso",
            "listo, te agrego al repo",
            "dale, cuadremos para mañana",
        ],
        "resolutions": [],
    },
    "ruido": {
        "weight": 0.07, "es_incidente": False,
        "severidad_pool": {},
        "openers": [
            "jajaja alguien vio el video que mandé",
            "buen finde a todos!",
            "{service} volvió a la normalidad, era una alerta vieja, falsa alarma",
        ],
        "followups": [
            "dale, buen finde!",
            "ah ok gracias por avisar",
        ],
        "resolutions": [],
    },
}

KB_TEMPLATES = {
    "indisponibilidad": ("caída total de {servicio} por pod en crashloop",
                          "deploy con configuración inválida", "rollback al release anterior"),
    "degradacion": ("degradación severa de latencia en {servicio}",
                     "query sin índice tras una migración", "se agregó índice y se optimizó la query"),
    "error_funcional": ("cálculo incorrecto en {servicio} para montos negativos",
                         "edge case no cubierto por tests", "fix desplegado y cobertura de test agregada"),
    "acceso_identidad": ("bloqueo masivo de login en {servicio}",
                          "desfase de reloj entre nodos de auth", "sincronización de NTP en todos los nodos"),
    "datos": ("registros faltantes en {servicio} tras el batch nocturno",
              "fallo silencioso del job de sincronización", "se agregó alertamiento al job y reconciliación manual"),
    "integracion_terceros": ("rechazo masivo de pagos por timeout del proveedor",
                              "incidente del lado del proveedor externo", "circuito de retry con backoff exponencial"),
    "capacidad": ("saturación de disco en {servicio}",
                  "logs de debug dejados activos en producción", "se desactivó el log verboso y se amplió cuota"),
    "seguridad": ("intentos de acceso desde IPs no reconocidas a {servicio}",
                  "credencial expuesta en un commit público", "rotación de credenciales y limpieza de historial git"),
}

# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

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

def msg(user_tuple, ts, texto):
    return {"autor": user_tuple[0], "rol": user_tuple[1], "timestamp": ts.isoformat(), "texto": texto}

# --------------------------------------------------------------------------
# Base de conocimiento de incidentes previos (para demo de RAG / mitigación)
# --------------------------------------------------------------------------

def build_kb(n=15):
    kb = []
    cats = list(KB_TEMPLATES.keys())
    for i in range(n):
        cat = random.choice(cats)
        servicio = random.choice(SERVICES)
        resumen_t, causa_t, solucion_t = KB_TEMPLATES[cat]
        fecha = random_timestamp(days_back=400)
        kb.append({
            "id": f"INC-{fecha.year}-{i+1:04d}",
            "servicio": servicio,
            "categoria": cat,
            "resumen": resumen_t.format(servicio=servicio),
            "causa_raiz": causa_t,
            "solucion": solucion_t,
            "fecha": fecha.isoformat(),
        })
    return kb

# --------------------------------------------------------------------------
# Generación de un hilo
# --------------------------------------------------------------------------

def build_thread(idx, category, kb):
    cfg = CATEGORIES[category]
    servicio = random.choice(SERVICES)
    participantes = random.sample(USERS, k=random.randint(2, 4))
    autor_principal = participantes[0]

    t0 = random_timestamp()
    ctx = {
        "service": servicio,
        "user": autor_principal[0],
        "user2": participantes[1][0] if len(participantes) > 1 else participantes[0][0],
        "hora": t0.strftime("%H:%M"),
    }

    mensajes = []
    cur_t = t0
    mensajes.append(msg(autor_principal, cur_t, random.choice(cfg["openers"]).format(**ctx)))

    n_followups = random.randint(1, min(4, len(cfg["followups"])))
    for tmpl in random.sample(cfg["followups"], k=n_followups):
        cur_t += timedelta(seconds=random.randint(30, 900))
        autor = random.choice(participantes)
        mensajes.append(msg(autor, cur_t, tmpl.format(**ctx)))

    menciona_prev, id_prev = False, None
    if cfg["es_incidente"] and kb and random.random() < 0.3:
        candidatos = [k for k in kb if k["servicio"] == servicio] or kb
        prev = random.choice(candidatos)
        id_prev, menciona_prev = prev["id"], True
        cur_t += timedelta(seconds=random.randint(30, 600))
        autor = random.choice(participantes)
        texto = f"esto me suena a {prev['id']}, {prev['resumen']}"
        mensajes.append(msg(autor, cur_t, texto))

    resuelto = False
    if cfg["resolutions"] and random.random() < 0.45:
        cur_t += timedelta(seconds=random.randint(120, 1800))
        autor = random.choice(participantes)
        mensajes.append(msg(autor, cur_t, random.choice(cfg["resolutions"]).format(**ctx)))
        resuelto = True

    severidad = weighted_choice(cfg["severidad_pool"]) if cfg["es_incidente"] else "n/a"
    tono = random.choices(["urgente", "neutral", "casual"], weights=[0.35, 0.4, 0.25], k=1)[0]
    deploy_rel = cfg["es_incidente"] and random.random() < 0.25

    return {
        "thread_id": f"DEVCHAT-{idx:04d}",
        "canal": random.choice(CHANNELS),
        "categoria_real": category,
        "es_incidente": cfg["es_incidente"],
        "severidad_real": severidad,
        "tono_percibido": tono,
        "servicio_afectado": servicio if cfg["es_incidente"] else None,
        "deploy_relacionado": deploy_rel,
        "menciona_incidente_previo": menciona_prev,
        "id_incidente_previo_referenciado": id_prev,
        "hilo_resuelto_en_chat": resuelto,
        "timestamp_inicio": t0.isoformat(),
        "duracion_minutos": round((cur_t - t0).total_seconds() / 60, 1),
        "mensajes": mensajes,
    }

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Generador de tickets sintéticos de dev chat")
    ap.add_argument("--n", type=int, default=40, help="cantidad de hilos a generar")
    ap.add_argument("--kb-n", type=int, default=15, help="cantidad de incidentes previos en la KB")
    ap.add_argument("--seed", type=int, default=None, help="semilla para reproducibilidad")
    ap.add_argument("--out", type=str, default="/mnt/user-data/outputs/dev_chat_tickets.jsonl")
    ap.add_argument("--kb-out", type=str, default="/mnt/user-data/outputs/kb_incidentes_previos.jsonl")
    ap.add_argument("--pretty", action="store_true", help="imprime los primeros 3 hilos en consola")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    kb = build_kb(args.kb_n)
    categorias = list(CATEGORIES.keys())
    pesos = [CATEGORIES[c]["weight"] for c in categorias]

    hilos = []
    for i in range(1, args.n + 1):
        cat = random.choices(categorias, weights=pesos, k=1)[0]
        hilos.append(build_thread(i, cat, kb))

    with open(args.out, "w", encoding="utf-8") as f:
        for h in hilos:
            f.write(json.dumps(h, ensure_ascii=False) + "\n")

    with open(args.kb_out, "w", encoding="utf-8") as f:
        for k in kb:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")

    conteo = {}
    for h in hilos:
        conteo[h["categoria_real"]] = conteo.get(h["categoria_real"], 0) + 1

    print(f"Generados {len(hilos)} hilos -> {args.out}")
    print(f"Generados {len(kb)} incidentes previos -> {args.kb_out}")
    print("Distribución por categoría:")
    for c, n in sorted(conteo.items(), key=lambda x: -x[1]):
        print(f"  {c:22s} {n}")

    if args.pretty:
        print("\n--- muestra ---")
        for h in hilos[:3]:
            print(f"\n[{h['thread_id']}] {h['canal']} | {h['categoria_real']} | "
                  f"incidente={h['es_incidente']} | severidad={h['severidad_real']} | tono={h['tono_percibido']}")
            for m in h["mensajes"]:
                print(f"  {m['timestamp'][11:16]} @{m['autor']}: {m['texto']}")

if __name__ == "__main__":
    main()
