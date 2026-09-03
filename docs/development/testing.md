# Estrategia de pruebas

## Suite rápida

```bash
python3 -m unittest discover -s tests -v
```

Cubre configuración, `.env`, contrato del proveedor, parser SSE, validación del
caso de uso y API HTTP real sobre un puerto efímero.

> Al 03-09-2026 falla `test_devkit_setup.ClaudeMcpConfigTests.test_claude_target_does_not_require_codex`:
> parchea `check_claude`, que ya no existe en `configurar-devkit-huawei.py`
> (se unificó en `check_client`). Es deuda de la prueba, no del script, y es
> anterior al flujo multiagente.

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
