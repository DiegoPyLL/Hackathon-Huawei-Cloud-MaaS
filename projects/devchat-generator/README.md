# Dev Chat Generator

Parte del **Incident Triage Agent** para el AI Agentic Hackathon (Huawei
Cloud MaaS, organiza Kostra): el canal de dev chat, con su generador batch y
su simulador en vivo. Contexto completo del proyecto, decisiones técnicas y
estado del checklist en [`CLAUDE.md`](CLAUDE.md) — este README es solo la
guía de "cómo lo levanto en mi máquina".

## Estructura

```
devchat-generator/
├── CLAUDE.md                        contexto del proyecto, stack, plan del día
├── docs/
│   └── taxonomia_incidentes.md      8 tipos de incidente + solicitud/ruido
├── channels/
│   └── devchat/
│       ├── NOTES.md                 particularidades de la señal de dev chat
│       ├── generator/               generador batch (dataset con groundtruth)
│       ├── live_simulator/          chat en vivo simulado (FastAPI + WS)
│       └── data/                    jsonl generados (batch y en vivo)
└── requirements.txt
```

`channels/email/` y `channels/monitoring/` todavía no existen — ver el
checklist en `CLAUDE.md` para lo que falta.

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

## Notas

El `.gitignore` de esta carpeta excluye `.venv/`, `__pycache__/` y los jsonl
que el simulador en vivo regenera en cada arranque (`devchat_live_public.jsonl`,
`devchat_live_groundtruth.jsonl`, `server.log`); el dataset del generador
batch (`dev_chat_tickets.jsonl`, `kb_incidentes_previos.jsonl`) sí queda
versionado porque es reproducible pero no se regenera solo.
