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

Python 3.9+. Sin dependencias externas. Funciona igual en Windows, macOS y Linux.

## Uso

Se puede ejecutar **desde cualquier directorio**: las rutas por defecto se
resuelven respecto al script, no respecto a donde lo lances. Los ejemplos usan la
raíz del repo.

```bash
# catálogo de escenarios (16, dos por cada tipo canónico)
python projects/monitoreo/generator/generate_monitoreo_dumps.py --list-escenarios

# dataset por defecto: 40 volcados en projects/monitoreo/data/, reproducible
python projects/monitoreo/generator/generate_monitoreo_dumps.py --seed 7

# además, un .md legible con cada volcado y su `esperado`
python projects/monitoreo/generator/generate_monitoreo_dumps.py \
  --md-out projects/monitoreo/data/ejemplos.md

# un volcado camino-feliz por cada escenario dado
python projects/monitoreo/generator/generate_monitoreo_dumps.py \
  --solo-escenario credential_stuffing_horizontal,disco_motor_datos
```

En Windows, `python` suele ser el ejecutable correcto; en Linux/macOS puede que
necesites `python3`.

| Flag | Default | Descripción |
| --- | --- | --- |
| `--n` | 40 | nº de volcados. El mínimo real es 16 (uno por escenario, para no dejar ningún tipo sin cubrir); el resto se reparte por segmentos |
| `--seed` | 7 | semilla RNG; misma semilla ⇒ mismo dataset |
| `--out` | `data/monitoreo_dumps.jsonl` del proyecto | salida JSONL. Una ruta relativa se resuelve desde tu directorio actual |
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

## Superficie pública (no romper)

`projects/bus-incidentes/bus.py` **importa este módulo** para no duplicar la
taxonomía: reutiliza los 16 escenarios canónicos como fuente de los incidentes
que reparte a todos los canales.

```python
from generate_monitoreo_dumps import ESCENARIOS, RUTEO_DEFECTO, SERVICIOS, Ids
```

Esos nombres —más `RUIDOS`— son API pública: renombrarlos o eliminarlos rompe el
bus. Están listados en `API_PUBLICA` y `--autotest` lo verifica.

```bash
# antes de commitear cualquier cambio al generador
python projects/monitoreo/generator/generate_monitoreo_dumps.py --autotest
```

Comprueba que los nombres públicos siguen ahí, que los 16 escenarios se
construyen y declaran groundtruth coherente, que cada ruido trae el dato que lo
descarta, y que un dataset completo cumple el contrato. No escribe nada.

## Auto-validación

Antes de escribir nada a disco, el generador comprueba su propia salida contra el
contrato del repo y **aborta sin escribir** si algo no cuadra: un fixture inválido
en disco es peor que un fallo declarado. Se verifica lo mismo que el servidor
valida de la respuesta del modelo:

- `tipo` dentro de los 8 canónicos.
- `especialistas` ⊆ `{dba, sysadmin, secops}`, entre 1 y 2, incluyendo siempre el
  especialista por defecto de la tabla de ruteo.
- `action_id` dentro del catálogo cerrado, y referido a un incidente que existe
  en el `ruteo` del mismo volcado.
- Identificadores (`ALRT-`, `HOST-`, `TRX-`, `SES-`, `CRED-`, `DEP-`) conformes a
  los patrones que valida el servidor.
- Los 8 tipos con al menos un caso (no se exige con `--solo-escenario`, que es un
  subconjunto deliberado).

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
