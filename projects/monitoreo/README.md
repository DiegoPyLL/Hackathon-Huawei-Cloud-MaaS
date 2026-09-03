# Generador del canal Monitoreo — Nortia Retail

Parte del **Incident Triage Agent** (AI Agentic Hackathon, Huawei Cloud MaaS,
organiza Kostra): el **canal `monitoreo`**, uno de los 3 canales de entrada
junto a `dev-chat` (`projects/devchat-generator/`) y `email-soporte`.

Genera **volcados de alertas** sintéticos con groundtruth, para medir al
Orquestador (triage + clasificación + separación de ruido) sin etiquetado manual.

> Fuente de verdad: `docs/` del repo. Este README es solo "cómo lo corro".
> Reglas del formato en [`NOTES.md`](NOTES.md).

## Cómo encaja

```
  ESTA PIEZA                        RESTO DEL EQUIPO
  ─────────────────────            ───────────────────────────────────────

  generate_monitoreo_dumps.py
        │  simula alertas de monitoreo
        │  de Nortia Retail (+ ruido)
        ▼
  data/monitoreo_dumps.jsonl
   { id, canal, segment, prompt, esperado }
        │  el `prompt` es el volcado que se pega tal cual
        ▼
  Orquestador (fase triage) ──▶ 8 tipos + descartados + ruteo
        │
        ▼
  DBA / SysAdmin / SecOps ──▶ causa raíz + acción del catálogo cerrado
        │
        ▼
  evaluación: salida  vs  `esperado`  (tipo · ruteo · descartados · acción)
```

`docs/architecture/flujo-agentes.md` tiene el flujo completo de 6 fases.

## Requisitos

Python 3.9+. Sin dependencias externas.

## Uso

```bash
cd generator

# catálogo de escenarios (16, dos por cada tipo canónico)
python generate_monitoreo_dumps.py --list-escenarios

# dataset por defecto: 40 volcados, reproducible
python generate_monitoreo_dumps.py --seed 7 \
  --out ../data/monitoreo_dumps.jsonl \
  --md-out ../data/ejemplos.md

# un volcado camino-feliz por cada escenario dado
python generate_monitoreo_dumps.py --solo-escenario credential_stuffing_horizontal,disco_motor_datos
```

| Flag | Default | Descripción |
| --- | --- | --- |
| `--n` | 40 | nº de volcados (16 de cobertura + resto repartido por segmentos) |
| `--seed` | 7 | semilla RNG; misma semilla ⇒ mismo dataset |
| `--out` | `../data/monitoreo_dumps.jsonl` | salida JSONL |
| `--md-out` | — | además, un `.md` legible con cada volcado y su `esperado` |
| `--solo-escenario a,b` | — | un volcado camino-feliz por cada id |
| `--pretty` | — | JSONL indentado |
| `--list-escenarios` | — | imprime el catálogo y sale |

## Estructura

```
monitoreo/
├── README.md          este archivo
├── NOTES.md           particularidades del canal + campos de groundtruth
├── generator/
│   └── generate_monitoreo_dumps.py
└── data/
    ├── monitoreo_dumps.jsonl   dataset (versionado: reproducible, no se regenera solo)
    └── ejemplos.md             render legible (opcional)
```

## Alineación con el repo

- **Empresa:** Nortia Retail (`docs/product/clasificacion-incidentes.md`), datos
  sintéticos; secretos con formato obviamente falso (`AKIA_EJEMPLO_1234`).
- **Tipos:** los 8 literales kebab del contrato (`docs/architecture/contratos-agentes.md`).
- **Ruteo:** cada `esperado.ruteo` sigue la tabla de `docs/architecture/flujo-agentes.md`.
- **Acciones:** `esperado.acciones_esperadas[].action_id` sale del catálogo cerrado.
- **IDs:** `ALRT-\d{1,6}`, `HOST-\d{1,6}`, `TRX-\d{1,6}`, `SES-\d{1,6}`,
  `CRED-\d{1,6}`, `DEP-\d{1,6}` — los patrones que valida el servidor.

Los `evals/*.json` del repo **no** se tocan desde aquí (son fixtures compartidos).
Curar un subconjunto e integrarlo es una decisión de equipo pendiente.
