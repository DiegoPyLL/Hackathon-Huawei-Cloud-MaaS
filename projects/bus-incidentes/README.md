# Bus de incidentes — la pieza que conecta todo

Antes, cada sistema inventaba sus propios incidentes al azar. El agente no podía
correlacionar nada porque no había nada que correlacionar: eran cuatro streams de
ruido independiente. El bus arregla eso — **un incidente nace una sola vez y cada
canal lo cuenta a su manera**.

```
                    projects/monitoreo/generator/
                    16 escenarios canónicos (tipo, severidad,
                    especialistas, acción esperada, líneas)
                              │
                              ▼
                    ┌───────────────────┐
                    │   BUS  :8010      │  INC-01 · datos · bd-clientes · alta
                    └─────────┬─────────┘
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   SEMÁFORO :8028       DEV-CHAT :8000       (email, pendiente)
   panel en rojo        alguien lo comenta   ticket de soporte
   + logs de evidencia  en #incidentes
          └───────────────────┼───────────────────┘
                              ▼
                     el agente correlaciona
                     las 3 señales en 1 incidente
```

## Levantar todo

```powershell
# desde la raíz del repo, una sola vez
python -m venv .venv
.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" httpx

# y después
.venv\Scripts\python.exe projects\bus-incidentes\levantar_todo.py
```

| Sistema | URL | Qué es |
| --- | --- | --- |
| Semáforo + logs | http://localhost:8028 | Dashboard de estado por servicio y consola de logs |
| Dev chat | http://localhost:8000 | Chat tipo Slack donde el equipo comenta los incidentes |
| Bus (API) | http://localhost:8010 | Sin UI; es la fuente de verdad |

## Endpoints del bus

| Ruta | Qué devuelve |
| --- | --- |
| `GET /api/incidentes/activos` | Los incidentes vivos ahora mismo |
| `GET /api/incidentes` | Todos, incluidos los ya resueltos |
| `GET /api/estado-servicios` | Estado por panel del semáforo |
| `GET /api/feed/monitoreo` | Las líneas de alerta como volcado, listo para la fase 1 del Orquestador |
| `GET /api/verdad` | **Groundtruth**: qué pasó de verdad y por qué canales se reportó cada cosa |
| `GET /api/escenarios` | Los 16 escenarios disponibles |
| `POST /api/incidentes/provocar` | Dispara un incidente a mano — `{"escenario": "caida_tras_deploy"}` |

## El botón de la demo

```bash
# provocar un incidente concreto y verlo aparecer en los 3 sistemas a la vez
curl -X POST http://localhost:8010/api/incidentes/provocar \
  -H "Content-Type: application/json" \
  -d '{"escenario": "credential_stuffing_horizontal"}'
```

Sin `escenario` elige uno al azar. La lista completa está en `GET /api/escenarios`.

## Decisiones que importan

**Los escenarios no se duplican, se importan.** El bus hace
`from generate_monitoreo_dumps import ESCENARIOS` — la taxonomía de 8 tipos, la
tabla de ruteo y el catálogo cerrado de acciones viven en un solo lugar
(`projects/monitoreo/`), alineados con `docs/architecture/contratos-agentes.md`.
Si alguien agrega un escenario ahí, el bus lo reparte solo.

**No todos los canales reportan todo.** El dev-chat comenta el ~80% de los
incidentes; el resto sale en monitoreo y en el semáforo pero nadie lo menciona en
el chat. Esa asimetría es deliberada: si los tres canales dijeran siempre lo
mismo, correlacionar sería trivial y el agente no demostraría nada. `reportado_en`
de cada incidente registra por dónde entró efectivamente.

**Los canales degradan solos.** Si el bus no está levantado, el semáforo se
queda en verde y el dev-chat sigue generando charla local. Ningún sistema se
cae porque falte otro — importa para no perder la demo por un proceso muerto.

**El groundtruth nunca viaja con la señal.** Ni el chat ni el semáforo exponen
`tipo` ni `severidad` en lo que el agente puede leer; eso vive aparte, en
`/api/verdad` y en los logs de groundtruth de cada canal. El agente clasifica sin
red, y después se puntúa contra la verdad.

## El camino de vuelta

`projects/agente-puente/` recoge las tres versiones del incidente y se las pasa
al agente (`src/maas_demo`) para que las correlacione:

```powershell
$env:MAAS_MODE="mock"; .venv\Scripts\python.exe -m src.maas_demo   # agente
.venv\Scripts\python.exe projects\agente-puente\puente.py          # corrida
```

## Pendiente

- **Email** (`projects/incident-agent/`): el pipeline Postmark → Supabase todavía
  no está desplegado (ver su README: faltan `supabase link`, los secrets, el
  deploy de la Edge Function y el webhook). Cuando lo esté, es un consumidor más:
  lee `GET /api/incidentes/activos` y redacta el ticket.
- **Agente en `live`**: hoy la corrida se prueba en `MAAS_MODE=mock`, que
  devuelve una respuesta determinista sin analizar. El análisis real necesita la
  API key de MaaS.
