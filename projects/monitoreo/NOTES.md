# Canal: Monitoreo

Particularidades de la señal de monitoreo y referencia de los campos de
groundtruth que emite el generador. La doctrina completa (taxonomía, tabla de
ruteo, catálogo de acciones) está en `docs/` del repo — este archivo solo
anota lo propio del canal.

## Lo que llega

Alertas estructuradas generadas automáticamente al cruzar un umbral: `alert_id`,
métrica, timestamp, host/servicio. Formato limpio y parseable, **pero es el
canal con más falsos positivos** — umbrales mal calibrados, jobs programados que
disparan alarmas, picos transitorios legítimos. Nunca se asume incidente real
solo porque una alerta se disparó (`docs/product/deteccion-incidentes.md`).

## Cómo llega

Un **volcado de texto plano**, una línea por alerta/evento, orden cronológico,
prefijo `MONITOREO HH:MM:SS` (UTC). Cabe entero en el prompt: no hay corpus ni
consultas — el Orquestador lo lee completo en la fase de triage.

Dos sub-estilos de línea, ambos presentes:

```
MONITOREO 09:52:14 alert=ALRT-9110 host=HOST-12 metric=cpu.pct value=97 sostenido=11min
MONITOREO 20:10:05 evento=login_fallo status=401 ip=203.0.113.47 ua=curl/8.4 user=admin
```

## Qué debe hacer el agente

1. Decidir **si hay incidente**: separar las alertas reales del ruido, citando
   el dato que descarta cada falso positivo.
2. Clasificar cada incidente real en **uno de los 8 tipos canónicos**.
3. Aplicar la **regla de desempate 4 vs 8**: acceso sospechoso es tipo 4 salvo
   intención maliciosa demostrada (patrón horizontal, viaje imposible, credencial
   filtrada).
4. Proponer ruteo según la tabla y, si procede, un `action_id` del catálogo
   cerrado.

## Formato de cada registro del dataset

Un objeto por línea en `data/monitoreo_dumps.jsonl`:

```json
{
  "id": "monitoreo-camino-feliz-01",
  "canal": "monitoreo",
  "segment": "camino-feliz",
  "prompt": "Volcado de Nortia Retail (UTC). MONITOREO ... | ... | Investiga este volcado.",
  "esperado": { ... }
}
```

### Campos de `esperado` (groundtruth)

| Campo | Cuándo | Contenido |
| --- | --- | --- |
| `incidentes` | volcados normales | nº de incidentes reales en el volcado |
| `ruteo` | siempre | `{ "INC-<slug>": { "tipo", "especialistas", "ataque_activo" } }` — `tipo` es el literal kebab del contrato; `especialistas` ⊆ `{dba, sysadmin, secops}` |
| `descartados_esperados` | siempre | lista de textos: cada falso positivo **con el dato que lo descarta**. Puede ir vacía |
| `acciones_esperadas` | siempre | lista de `{ incidente, action_id, params_clave }`; `action_id` del catálogo cerrado. `[]` si no hay acción clara |
| `nota` | siempre | por qué se clasifica así (para quien revisa) |
| `incidentes_detectados` / `incidentes_analizados` / `diferidos` / `diferidos_esperados` | solo `segment == tope-presupuesto` | prueba el recorte por `MAX_INCIDENTES=6` y el reporte de diferidos |

`esperado` **no** es el Entregable de Triage (contrato A) ni el Hallazgo
(contrato B): es la referencia contra la que se puntúa la salida del Orquestador.
`ruteo` mapea a `incidentes[].tipo` + `.especialistas`; `descartados_esperados` a
`descartados[]`; `acciones_esperadas` a la acción del Hallazgo del especialista.

## Segmentos

| `segment` | Qué prueba |
| --- | --- |
| `camino-feliz` | 1 incidente claro (+0–1 ruido). Cobertura: 1 por cada uno de los 16 escenarios |
| `falso-positivo` | 1 incidente real ahogado en 2–3 señales que parecen incidente |
| `ambiguedad` | el dato que decide (ataque vs scraper, etc.) **no** está en el volcado |
| `multi-incidente` | 2–3 incidentes de tipos distintos + ruido — rompe clasificadores ingenuos |
| `entrada-hostil` | incluye una línea `# SYSTEM OVERRIDE ...` que debe ignorarse |
| `datos-incompletos` | el colector entregó líneas truncadas (`... frag ...`, `alert=ALRT-77??`) |
| `tope-presupuesto` | 7–8 incidentes reales > `MAX_INCIDENTES=6`: fuerza priorizar y declarar diferidos |

## Limitaciones conocidas

- El groundtruth de `especialistas` sigue la tabla de ruteo por defecto + el
  segundo especialista obvio; un caso podría admitir otro ruteo defendible.
- `datos-incompletos` trunca al azar: a veces el fragmento que sobra sigue siendo
  suficiente para clasificar. Es realista, pero si estorba, subir el umbral en
  `construir_volcado()`.
- `--multicanal` (intercalar dev-chat / acceso como ruido) **no** está
  implementado todavía: los volcados son `MONITOREO` puro. Los volcados
  consolidados de 3 canales viven en `evals/casos-multi-incidente.json` y se
  arman combinando la salida de los tres generadores de canal.

## Pendiente

- [ ] `--multicanal`: ruido de otros canales intercalado.
- [ ] Curar un subconjunto e integrarlo a `evals/` (decisión de equipo: son
      fixtures compartidos).
