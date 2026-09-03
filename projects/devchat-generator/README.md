# Incident Triage Agent

Agente de triage de incidentes para el AI Agentic Hackathon (Huawei Cloud
MaaS, organiza Kostra). Contexto completo del proyecto, decisiones técnicas
y estado del checklist en [`CLAUDE.md`](CLAUDE.md) — este README es solo la
guía de "cómo lo levanto en mi máquina".

> **Antes de seguir con esto, leer [`PENDIENTE.md`](PENDIENTE.md).** Documenta
> lo que falta y por qué importa cada cosa — lo más urgente es que el agente
> nunca se probó en modo `live`, así que todavía no hay ningún dato sobre si
> clasifica bien.

> **Nota sobre el nombre de la carpeta:** se llama `devchat-generator` porque
> cuando se subió solo tenía el canal de dev chat. Hoy contiene el agente
> completo y los tres canales; el nombre quedó corto y no se renombró para no
> romper rutas a mitad del evento.

## Estructura

```
incident-triage-agent/
├── CLAUDE.md                        contexto del proyecto, stack, plan del día
├── docs/
│   ├── taxonomia_incidentes.md      8 tipos de incidente + solicitud/ruido
│   └── pitch.md                     guion de pitch (5 min)
├── agent/
│   ├── schema.py                    esquema canónico de incidente
│   ├── maas_client.py               cliente Huawei Cloud MaaS (OpenAI-compatible)
│   ├── kb.py                        base de conocimiento + retrieval (RAG)
│   ├── tools.py                     classify + search_similar + consolidate
│   ├── loop.py                      loop del agente (classify → RAG → consolidate)
│   ├── correlate.py                 correlación/deduplicación cross-canal
│   └── load_senales.py              cargador multi-canal (devchat + email + monitoring)
├── channels/
│   ├── devchat/
│   │   ├── NOTES.md                 particularidades de la señal de dev chat
│   │   ├── generator/               generador batch (dataset con groundtruth)
│   │   ├── live_simulator/          chat en vivo simulado (FastAPI + WS)
│   │   └── data/                    jsonl generados (batch y en vivo)
│   ├── email/
│   │   ├── NOTES.md
│   │   ├── generator/               generador de tickets de email
│   │   └── data/
│   └── monitoring/
│       ├── NOTES.md
│       ├── generator/               generador de alertas de monitoring
│       └── data/
├── demo/
│   ├── server.py                    demo UI del agente (FastAPI + WS)
│   └── static/                      frontend del agente
└── requirements.txt
```

## Requisitos
- Python 3.10+ (se probó con 3.14 en Windows)
- Sin dependencias externas más allá de `requirements.txt` — no necesita
  Docker ni nada corriendo aparte

## Setup (una vez por máquina)

Desde la raíz del proyecto:

```bash
python -m venv .venv
```

Activar el entorno:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

## Correr el simulador de dev chat en vivo

Es la pieza que hoy se puede levantar y ver funcionando: un chat tipo Slack
que se genera solo (charla normal + incidentes reales, intercalados, sin
etiquetas visibles) y sirve de fuente de señal para el agente de triage.

```bash
cd channels/devchat/live_simulator
uvicorn server:app --reload --port 8000
```

Abrir [http://localhost:8000](http://localhost:8000). Detalle de diseño,
endpoints (`/api/history`, `/api/stats`, `/ws`) y por qué el feed público no
lleva groundtruth: [`channels/devchat/live_simulator/README.md`](channels/devchat/live_simulator/README.md).

## Correr el generador batch de dev chat

Genera un dataset estático (no en vivo) de hilos con groundtruth, útil para
medir precisión del clasificador contra algo objetivo:

```bash
cd channels/devchat/generator
python generate_devchat_tickets.py --n 60 --seed 7 \
  --out ../data/dev_chat_tickets.jsonl \
  --kb-out ../data/kb_incidentes_previos.jsonl
```

Detalle de los campos de groundtruth y limitaciones conocidas en
[`channels/devchat/NOTES.md`](channels/devchat/NOTES.md).

## Correr el generador de email

```bash
cd channels/email/generator
python generate_email_tickets.py --n 40 --seed 7 --out ../data/email_tickets.jsonl
```

## Correr el generador de monitoring

```bash
cd channels/monitoring/generator
python generate_monitoring_alerts.py --n 40 --seed 7 --out ../data/monitoring_alerts.jsonl
```

## Correr la demo del agente

Carga señales de los tres canales, las procesa con el agente (MaaS), y muestra
los incidentes consolidados en una UI web con streaming en vivo:

```bash
cd demo
python -m uvicorn server:app --reload --port 8001
```

Abrir [http://localhost:8001](http://localhost:8001) y presionar "Ejecutar Triage".

Requiere que las variables de entorno de MaaS estén configuradas
(`MAAS_API_KEY`, `MAAS_BASE_URL`, `MAAS_MODEL`). Ver `.env` en la raíz del
workspace.

Guion de pitch en [`docs/pitch.md`](docs/pitch.md).

## Nota para el repo grupal

Esta carpeta no tiene `.git` propio todavía — está pensada para copiarse
directo dentro del repo del equipo. El `.gitignore` ya excluye `.venv/`,
`__pycache__/` y los jsonl que el simulador en vivo regenera en cada
arranque (`devchat_live_public.jsonl`, `devchat_live_groundtruth.jsonl`,
`server.log`); el dataset del generador batch (`dev_chat_tickets.jsonl`,
`kb_incidentes_previos.jsonl`) sí queda versionado porque es reproducible
pero no se regenera solo.
