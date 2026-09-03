# Estrategia de pruebas

## Suite rápida

```bash
python3 -m unittest discover -s tests -v
```

Cubre configuración, `.env`, contrato del proveedor, parser SSE, validación del
caso de uso, API HTTP real sobre un puerto efímero, el cliente de Supabase, los
contratos compartidos entre piezas y el generador del canal monitoreo.

> Actualizado el 03-09-2026: la suite está en verde (100 pruebas, 10 omitidas).
> El fallo de `test_devkit_setup` que este documento describía ya no existe —
> lo corrigió `27a8fd2` al pasar de `check_claude` a `check_client`.
>
> Las 10 omitidas son las de `test_full_flow.py` y `OrquestadorSinDerivaTests`
> que dependen de `src/maas_demo/orchestrator.py`, todavía en la rama
> `agente-orquestrador-*`. Se saltan declarando el motivo en vez de romper la
> colección, y **se reactivan solas** cuando esa rama entre a `main`. Era el
> prerrequisito de `ci.yml`
> ([ADR-0006](../architecture/decisions/0006-ejecucion-programada-y-manual.md)):
> un workflow que nace en rojo deja de ser una señal.

### Categorías

`ejecutar-corrida.py --con-tests` corre la misma suite y la agrupa, para ver de
un vistazo qué área está cubierta y qué se omitió y por qué:

| Categoría | Qué cubre |
| --- | --- |
| `vertical-slice` | config, dotenv, proveedor, servicio, servidor HTTP |
| `conexion-supabase` | cliente PostgREST: cabeceras, errores, que la key nunca se filtre |
| `contrato-canonico` | taxonomía, catálogo de acciones, API pública del generador, esquema de `evals/` |
| `generador-monitoreo` | escenarios, determinismo, dataset versionado, validador |
| `corrida-unica` | el entrypoint: carga de volcados, contraste, categorización |
| `flujo-agente` | contratos del orquestador (omitido hasta que llegue a `main`) |

## Integración continua

Dos workflows, separados porque tienen fronteras de confianza distintas
([ADR-0006](../architecture/decisions/0006-ejecucion-programada-y-manual.md)).

**`.github/workflows/ci.yml`** — en cada push y cada PR, **sin secretos**:

1. `python -m unittest discover -s tests -v`
2. `evaluar.py --mode mock`
3. `ejecutar-corrida.py --mode mock --con-tests`
4. `generate_monitoreo_dumps.py --autotest`

Sin `pip install`: el proyecto es stdlib pura. Las acciones van pineadas a SHA y
el submódulo `.claude/skills` no se clona, porque nada del código lo lee.

**`.github/workflows/verificar-supabase.yml`** — `workflow_dispatch` y a diario,
**con secretos** (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`), nunca disparado
por un `pull_request`. Corre `ejecutar-corrida.py --verificar-almacen`, que
cuenta las filas de cada tabla y falla declarando si la credencial no sirve.

La conexión a Supabase se prueba en los dos sitios, pero de forma distinta: en
`ci.yml` con un `opener` falso, que ejercita cabeceras y errores sin red; en el
workflow programado contra la base real. Un fallo de conexión nunca se presenta
como éxito.

## Corrida única

```bash
python3 scripts/ejecutablesBase/ejecutar-corrida.py --mode mock --con-tests
python3 scripts/ejecutablesBase/ejecutar-corrida.py --caso monitoreo-camino-feliz-01
python3 scripts/ejecutablesBase/ejecutar-corrida.py --verificar-almacen
python3 scripts/ejecutablesBase/ejecutar-corrida.py --leer-tabla incidentes
```

Ejecuta la suite (categorizada), el flujo del agente sobre los volcados de
`projects/monitoreo/data/monitoreo_dumps.jsonl` y la persistencia, en un solo
comando. Los tests van primero: si fallan, no se gasta saldo en una corrida que
ya sabemos rota. A diferencia de `evaluar.py`, contrasta la salida contra el
bloque `esperado` de cada volcado.

## Evaluación GenAI

```bash
python3 scripts/ejecutablesBase/evaluar.py --mode mock
python3 scripts/ejecutablesBase/evaluar.py --mode live --json-out evals/results/live.json
```

`mock` prueba determinismo y contrato. `live` mide el proveedor y modelo reales.
Los resultados no son intercambiables y siempre registran el modo.

Antes de cambiar prompts, modelo o parámetros, ejecutar el baseline y comparar los
mismos casos.

### Datasets

| Archivo | Qué cubre |
| --- | --- |
| `evals/cases.json` | 11 casos de un incidente cada uno: camino feliz, falsos positivos, ambigüedad, entrada hostil, escalación |
| `evals/casos-multi-incidente.json` | 4 volcados con varios incidentes, para ejercitar el despacho: fan-out completo, dos especialistas sobre un mismo incidente, camino secuencial y tope de presupuesto |

Los casos multi-incidente llevan un bloque `esperado` con el ruteo, el número de
tareas y el número de llamadas que el flujo debería producir. `evaluar.py` lo
ignora —solo lee `id`, `segment` y `prompt`—, pero es lo que hace verificable a
mano el diseño de
[`../architecture/flujo-agentes.md`](../architecture/flujo-agentes.md):

```bash
python3 scripts/ejecutablesBase/evaluar.py --mode mock --cases evals/casos-multi-incidente.json
```

### Comparar modelo por rol

`MAAS_MODELO_TRIAGE`, `MAAS_MODELO_ESPECIALISTA` y `MAAS_MODELO_CONSOLIDACION` usan
por defecto el mejor modelo disponible
([ADR-0003](../architecture/decisions/0003-orquestacion-multiagente.md)). La
evaluación debe poder correr la misma batería con distintas combinaciones, pero con
una asimetría deliberada:

**La carga de la prueba está en la degradación.** No se trata de justificar por qué
se usa el modelo bueno, sino de demostrar —con casos, no con impresiones— que un rol
concreto no pierde calidad con uno más barato. Un empate en la batería no basta si
los casos difíciles (`evidencia-insuficiente`, `credencial-vencida-vs-fuerza-bruta`,
`instruccion-hostil-en-logs`) son justo donde se separa un modelo del otro.

Un baseline no comparable no sirve: los resultados registran siempre el modelo de
cada rol, igual que registran el modo.

## Smoke test desplegado

```bash
python3 scripts/ejecutablesBase/prueba-humo.py --url https://URL --require-mode live
```

La opción `--require-mode live` es obligatoria para afirmar que la integración
desplegada funciona contra el proveedor real y no contra la simulación.
