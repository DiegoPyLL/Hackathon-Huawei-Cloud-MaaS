#!/usr/bin/env python3
"""
Generador de alertas de monitoring sintéticas para probar el clasificador/triage.

Cada alerta trae groundtruth (categoria_real, es_incidente, severidad_real,
alert_state) para medir precisión del agente.

Las alertas con alert_state="resolved" son ruido (la alerta se recuperó sola,
no requiere acción) — mide falsos positivos si el agente las trata como
incidentes activos.

Uso:
    python generate_monitoring_alerts.py
    python generate_monitoring_alerts.py --n 40 --seed 7 --pretty
"""

import argparse
import json
import random
from datetime import datetime, timedelta

SERVICES = [
    "checkout", "auth-service", "api-gateway", "pagos", "notificaciones",
    "reportes", "bd-clientes", "batch-facturacion", "login-web",
    "app-movil", "cache-redis", "cola-mensajes",
]

ENVIRONMENTS = ["production", "production", "production", "staging"]

CATEGORIES = {
    "indisponibilidad": {
        "weight": 0.20, "es_incidente": True,
        "severidad_pool": {"critica": 0.5, "alta": 0.35, "media": 0.15},
        "alert_names": [
            "ServiceDown",
            "HealthcheckFailing",
            "NoHealthyUpstreams",
            "PodCrashLooping",
        ],
        "metrics": [
            ("up", 0, 1, "service {service} is down (up=0)"),
            ("http_success_rate", 0.0, 0.99, "success rate dropped to {value}"),
            ("healthy_instances", 0, 2, "no healthy instances for {service}"),
        ],
    },
    "degradacion": {
        "weight": 0.18, "es_incidente": True,
        "severidad_pool": {"alta": 0.3, "media": 0.5, "baja": 0.2},
        "alert_names": [
            "HighLatency",
            "P95LatencyAboveThreshold",
            "SlowResponseTime",
            "ElevatedErrorRate",
        ],
        "metrics": [
            ("http_p95_latency_ms", 3500, 500, "p95 latency at {value}ms (threshold 500ms)"),
            ("http_error_rate", 0.15, 0.01, "error rate at {value:.0%} (threshold 1%)"),
            ("request_duration_avg_ms", 2800, 300, "avg duration {value}ms (normal 300ms)"),
        ],
    },
    "capacidad": {
        "weight": 0.15, "es_incidente": True,
        "severidad_pool": {"alta": 0.3, "media": 0.4, "baja": 0.3},
        "alert_names": [
            "DiskSpaceLow",
            "HighMemoryUsage",
            "ConnectionPoolExhausted",
            "RateLimitExceeded",
        ],
        "metrics": [
            ("disk_usage_percent", 95, 80, "disk at {value}% (threshold 80%)"),
            ("memory_usage_percent", 92, 75, "memory at {value}% (threshold 75%)"),
            ("db_connections_used", 98, 50, "connection pool at {value}/100"),
        ],
    },
    "seguridad": {
        "weight": 0.08, "es_incidente": True,
        "severidad_pool": {"critica": 0.4, "alta": 0.4, "media": 0.2},
        "alert_names": [
            "BruteForceLoginDetected",
            "SuspiciousIPDetected",
            "CredentialLeakDetected",
        ],
        "metrics": [
            ("failed_login_rate_per_min", 150, 5, "failed logins at {value}/min (threshold 5)"),
            ("suspicious_ip_count", 12, 0, "{value} suspicious IPs detected"),
        ],
    },
    "integracion_terceros": {
        "weight": 0.10, "es_incidente": True,
        "severidad_pool": {"alta": 0.4, "media": 0.4, "baja": 0.2},
        "alert_names": [
            "ExternalApiTimeout",
            "WebhookDeliveryFailing",
            "PaymentGatewayError",
        ],
        "metrics": [
            ("external_api_timeout_rate", 0.8, 0.05, "external API timeout rate at {value:.0%}"),
            ("webhook_failures", 45, 0, "{value} webhook delivery failures"),
        ],
    },
    "acceso_identidad": {
        "weight": 0.07, "es_incidente": True,
        "severidad_pool": {"alta": 0.3, "media": 0.5, "baja": 0.2},
        "alert_names": [
            "MFAGenerationFailing",
            "TokenValidationErrors",
            "AuthServiceDown",
        ],
        "metrics": [
            ("auth_error_rate", 0.25, 0.01, "auth error rate at {value:.0%}"),
            ("mfa_failure_rate", 0.30, 0.02, "MFA failure rate at {value:.0%}"),
        ],
    },
    "ruido": {
        "weight": 0.22, "es_incidente": False,
        "severidad_pool": {},
        "alert_names": [
            "ServiceDown",
            "HighLatency",
            "DiskSpaceLow",
            "HighMemoryUsage",
        ],
        "metrics": [
            ("up", 1, 0, "service {service} recovered (up=1)"),
            ("http_p95_latency_ms", 450, 500, "latency back to normal ({value}ms)"),
        ],
    },
}


def weighted_choice(pool: dict):
    items, weights = zip(*pool.items())
    return random.choices(items, weights=weights, k=1)[0]


def random_timestamp(days_back=30):
    now = datetime.now()
    delta_days = random.randint(0, days_back)
    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    ts = now - timedelta(days=delta_days)
    return ts.replace(hour=hour, minute=minute, second=0, microsecond=0)


def build_alert(idx, category):
    cfg = CATEGORIES[category]
    servicio = random.choice(SERVICES)
    env = random.choice(ENVIRONMENTS)
    t0 = random_timestamp(days_back=30)

    alert_name = random.choice(cfg["alert_names"])
    metric_name, metric_value, threshold, desc_template = random.choice(cfg["metrics"])

    if category == "ruido":
        alert_state = "resolved"
        es_incidente = False
        severidad = "n/a"
    else:
        alert_state = "firing"
        es_incidente = True
        severidad = weighted_choice(cfg["severidad_pool"])

    description = desc_template.format(service=servicio, value=metric_value)

    labels = {
        "service": servicio,
        "environment": env,
        "severity": severidad if es_incidente else "info",
        "alertname": alert_name,
    }

    annotations = {
        "description": description,
        "runbook_url": f"https://runbooks.internal/{servicio}/{alert_name.lower()}",
        "summary": f"{alert_name} on {servicio} ({env})",
    }

    return {
        "alert_id": f"ALERT-{idx:04d}",
        "categoria_real": category,
        "es_incidente": es_incidente,
        "severidad_real": severidad,
        "alert_state": alert_state,
        "servicio_afectado": servicio if es_incidente else None,
        "environment": env,
        "alert_name": alert_name,
        "metric": {
            "name": metric_name,
            "value": metric_value,
            "threshold": threshold,
        },
        "labels": labels,
        "annotations": annotations,
        "timestamp": t0.isoformat(),
    }


def main():
    ap = argparse.ArgumentParser(description="Generador de alertas de monitoring sintéticas")
    ap.add_argument("--n", type=int, default=40, help="cantidad de alertas a generar")
    ap.add_argument("--seed", type=int, default=None, help="semilla para reproducibilidad")
    ap.add_argument("--out", type=str, default="../data/monitoring_alerts.jsonl")
    ap.add_argument("--pretty", action="store_true", help="imprime las primeras 3 alertas en consola")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    categorias = list(CATEGORIES.keys())
    pesos = [CATEGORIES[c]["weight"] for c in categorias]

    alerts = []
    for i in range(1, args.n + 1):
        cat = random.choices(categorias, weights=pesos, k=1)[0]
        alerts.append(build_alert(i, cat))

    with open(args.out, "w", encoding="utf-8") as f:
        for a in alerts:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")

    conteo = {}
    for a in alerts:
        conteo[a["categoria_real"]] = conteo.get(a["categoria_real"], 0) + 1

    print(f"Generadas {len(alerts)} alertas -> {args.out}")
    print("Distribución por categoría:")
    for c, n in sorted(conteo.items(), key=lambda x: -x[1]):
        print(f"  {c:22s} {n}")

    if args.pretty:
        print("\n--- muestra ---")
        for a in alerts[:3]:
            print(f"\n[{a['alert_id']}] {a['categoria_real']} | "
                  f"incidente={a['es_incidente']} | severidad={a['severidad_real']} | "
                  f"state={a['alert_state']}")
            print(f"  Alert: {a['alert_name']} on {a['servicio_afectado']} ({a['environment']})")
            print(f"  Metric: {a['metric']['name']}={a['metric']['value']} (threshold {a['metric']['threshold']})")
            print(f"  Desc: {a['annotations']['description']}")


if __name__ == "__main__":
    main()
