# 0003 — Orquestación multiagente con cuatro roles

> Estado: Aceptada · Fecha: 03-09-2026

Supera **una parte** del [0001](0001-vertical-slice-maas.md): la alternativa
descartada "añadir RAG o agentes desde el inicio", únicamente en lo relativo a
agentes. RAG y base vectorial siguen fuera de alcance, ahora por una razón técnica
(ver Decisión). El contrato `ChatProvider`, los adaptadores separados, el modo
visible y la ausencia de fallback automático siguen vigentes.

## Contexto

El vertical slice resuelve un incidente con **una sola llamada** al modelo: el
`SYSTEM_PROMPT` de `service.py` lleva el catálogo condensado completo y devuelve
las cinco secciones en texto. Eso demostró el contrato, que era su objetivo, pero
dejó tres brechas medibles:

1. **Todo el catálogo entra en cada request, sea o no pertinente.** Un incidente de
   capacidad llega al modelo acompañado de las tablas de ransomware, BEC y robo de
   sesión. Eso es ruido que el modelo tiene que atravesar para llegar a lo suyo, y
   ningún rol puede especializarse porque todos son el mismo. Que además se pague
   en cada llamada es la consecuencia menor.
2. **No hay razonamiento distribuido visible.** El modelo decide todo por dentro;
   lo único observable es el texto final. El diferenciador declarado del proyecto
   —dejar visible qué se investigó y qué se descartó— depende de la buena voluntad
   del prompt.
3. **Un volcado con varios incidentes se trata como uno solo.** No hay forma de
   priorizar, ni de decir "esto no lo alcancé a mirar".

El 0001 descartó agentes porque "no existe todavía una brecha evaluada que
justifique esa complejidad". Las tres brechas de arriba son esa justificación.

## Decisión

Se adoptó un flujo híbrido fan-out / fan-in con **exactamente cuatro roles**:
Orquestador, DBA, SysAdmin y SecOps. El Orquestador clasifica y delega en una
primera llamada, los especialistas investigan en paralelo acotado, y el
Orquestador consolida en una última llamada.

El detalle del flujo, sus fases y sus topes está en
[`flujo-agentes.md`](../flujo-agentes.md); los contratos JSON entre roles, en
[`contratos-agentes.md`](../contratos-agentes.md).

Tres propiedades que definen la decisión:

**El despacho lo hace el servidor, no el modelo.** El Orquestador *propone* qué
especialistas necesita cada incidente; el servidor valida esa propuesta contra la
tabla de ruteo y contra un presupuesto de llamadas. Un modelo que pida cuarenta
especialistas no obtiene cuarenta llamadas.

**Sigue sin haber RAG.** Kostra no ofrece recuperación: es inferencia pura. Todo
lo que el modelo puede usar viaja en el prompt. Lo que cambia respecto al agente
único no es de dónde sale el conocimiento, sino **cuánto de él se envía en cada
llamada**: cada especialista lleva solo su tajada del catálogo de
`deteccion-incidentes.md`. Con una ventana de un millón de tokens eso no resuelve un
límite de contexto — reduce el ruido que cada especialista tiene que atravesar para
llegar a lo suyo, y de paso abarata la llamada.

**La calidad manda sobre el costo, y por eso el modelo por defecto es el mejor
disponible en los tres roles.** Variables nuevas, todas con respaldo en `MAAS_MODEL`:

| Variable | Rol | Valor por defecto |
| --- | --- | --- |
| `MAAS_MODELO_TRIAGE` | Orquestador, fase de triage | `deepseek-v4-pro` |
| `MAAS_MODELO_ESPECIALISTA` | DBA, SysAdmin, SecOps | `deepseek-v4-pro` |
| `MAAS_MODELO_CONSOLIDACION` | Orquestador, fase de consolidación | `deepseek-v4-pro` |

El razonamiento, rol por rol:

- **Triage.** Es el rol donde un error cuesta más, porque **se propaga**. Una
  clasificación equivocada despacha el incidente al especialista equivocado, y
  ningún especialista posterior puede corregir una premisa que no ve. Ahorrar aquí
  es ahorrar en el cimiento.
- **Especialistas.** Producen el razonamiento con evidencia citada y las hipótesis
  descartadas, que **es el producto**, no un paso intermedio. Que la salida sea JSON
  estructurado dice algo del formato, no de la dificultad del juicio que hay detrás.
- **Consolidación.** Es lo que lee una persona y por lo que se juzga el sistema.

La palanca de rendimiento de este diseño **no es el modelo, es la arquitectura**: el
fan-out corre los especialistas en paralelo, así que el tiempo de resolución de un
incidente masivo lo marca el especialista más lento y no la suma de todos. Esa
ganancia es estructural y no se paga con calidad, que es la razón por la que existe
el flujo.

Las tres variables siguen existiendo, pero su propósito se invierte respecto a la
intuición inicial: no están para abaratar por defecto, sino para que una evaluación
pueda **demostrar** que algún rol tolera un modelo más barato sin perder calidad. La
carga de la prueba recae en la degradación, no en la calidad. Un ADR posterior podrá
fijar una combinación mixta si la evidencia la respalda.

## Alternativas descartadas

| Alternativa | Por qué se descartó |
| --- | --- |
| Mantener el agente único | No cierra ninguna de las tres brechas del contexto; el catálogo completo se paga en cada llamada |
| Lanzar los tres especialistas en paralelo sobre el ticket crudo | Dos de los tres producirían un análisis sin fundamento sobre un incidente que no es de su dominio, y el fan-in tendría que distinguir ese ruido del hallazgo real. Sale caro, pero sobre todo sale peor |
| Decenas de agentes especializados | Multiplica los puntos de falla y vuelve ilegibles las métricas; cuatro roles cubren los dominios que la taxonomía de ocho tipos realmente distingue |
| Flujo puramente secuencial entre los cuatro | Un incidente masivo que toca red y seguridad a la vez se resolvería en serie, alargando el tiempo de resolución sin ahorrar llamadas |
| Dejar que el modelo decida cuántos agentes abrir | Convierte el presupuesto en una sugerencia; una inyección en los logs podría inflar el gasto |
| Modelo barato por defecto en el fan-out, para abaratar la corrida | Optimiza el costo antes que el rendimiento, que es el orden inverso al que fija `CLAUDE.md`. El triage además propaga sus errores: ahorrar ahí degrada todo lo que venga después |
| Fijar ya una combinación mixta de modelos como decisión cerrada | No hay medición todavía; sería una preferencia disfrazada de decisión. Las variables quedan para que la evidencia decida, con la carga de la prueba en la degradación |

## Consecuencias

**A favor:** el razonamiento queda partido en artefactos observables —un entregable
de triage, N hallazgos, un reporte— en vez de ocurrir dentro de una sola respuesta.
El gasto pasa a ser acotable por diseño (topes de incidentes, de tareas y de
llamadas) y estimable antes de implementar. Un volcado con varios incidentes se
prioriza por severidad y lo que no entra se declara diferido en vez de perderse.

**En contra:** más superficie que puede fallar y más latencia total en el peor caso.
Aparece una clase de fallo que antes no existía —el modelo devuelve JSON que no
valida contra el contrato— y hay que tratarla sin inventar un entregable de
reemplazo. Y una corrida consume ahora varias unidades del saldo prepago en vez de
una, lo que multiplica el efecto de un `402` a media ejecución.

Sobre el costo: con `pro` en los tres roles una corrida de referencia sale unas 2,9
veces más cara que el agente único al que reemplaza. Se acepta como el precio de la
calidad y del razonamiento observable — pero no es gratis, y el saldo de Kostra es
prepago y compartido con el chat web, así que el tope de llamadas por corrida deja
de ser una medida de ahorro y pasa a ser una medida de **disponibilidad**: evita que
una entrada anómala agote el saldo antes de una demostración. El detalle está en
[`flujo-agentes.md`](../flujo-agentes.md).

**Coste de revertir:** medio. El endpoint del agente único (`POST /api/chat/stream`)
se mantiene intacto y con él las evaluaciones y el smoke test actuales, así que
volver atrás es dejar de usar el endpoint nuevo. Lo que no se revierte gratis son
los documentos y los casos de evaluación escritos alrededor del flujo.
