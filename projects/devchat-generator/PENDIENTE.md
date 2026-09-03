# Lo que falta — estado al cierre

Este documento es para quien tome el proyecto después. Dice qué está hecho, qué
no, y **por qué cada cosa que falta importa**. Ordenado por lo que más cuesta si
se deja así.

Rúbrica del evento, para calibrar prioridades:

| Categoría | Peso |
| --- | ---: |
| Tareas exitosas/correctas | 30% |
| Comportamiento del agente y autonomía | 25% |
| Uso de herramientas y orquestación | 15% |
| Gestión de la ambigüedad y fallos | 10% |
| Fiabilidad y prevención de alucinaciones | 10% |
| UX y calidad de la demostración | 5% |
| Creatividad | 5% |

---

## 1. Nunca se probó en `live` — no sabemos si clasifica bien

**Estado:** todo el flujo se probó en `mock`, que devuelve respuestas enlatadas
sin analizar nada. La `MAAS_API_KEY` **ya está configurada** en el `.env` de la
raíz del repo, así que no hay bloqueo — simplemente no se corrió.

**Por qué importa:** es el 30% de la rúbrica. Hoy no existe un solo dato que
diga si el agente clasifica bien o solo produce texto plausible.

**Cómo resolverlo:**
```powershell
$env:MAAS_MODE="live"
.venv\Scripts\python.exe projects\agente-puente\puente.py
```
La corrida cierra sola con el contraste contra el groundtruth (tipos acertados,
no detectados, inventados). Ese número es la evidencia que falta.

---

## 2. El model routing no existe, pero el pitch lo afirma

**Estado:** `agent/maas_client.py` define `model_cheap` y `model_strong`, pero
ambos caen al mismo valor por defecto (`MAAS_MODEL`), y el `.env` no define
`MAAS_MODEL_CHEAP` ni `MAAS_MODEL_STRONG`. El docstring del archivo menciona
`deepseek-v4-flash` y `qwen3-32b`, que el código nunca usa.

**Por qué importa:** el argumento de costo del pitch ("modelo barato para
clasificar, fuerte solo para consolidar") hoy es falso. Si un juez pide
demostrarlo, no hay nada que mostrar.

**Cómo resolverlo:** dos líneas en el `.env` de la raíz:
```
MAAS_MODEL_CHEAP=<modelo barato disponible en MaaS>
MAAS_MODEL_STRONG=<modelo fuerte>
```
Y corregir el docstring para que nombre los modelos reales. Si se decide no
hacer routing, **sacar la afirmación de la slide** — es peor afirmarlo y que no
sea cierto que no tenerlo.

---

## 3. Categoría desconocida se convierte en "ruido" en silencio

**Estado:** `agent/loop.py:42-46`. Si el modelo devuelve una categoría fuera de
la taxonomía, `_safe_categoria` la reemplaza por `Categoria.ruido`, que además
significa "no es incidente". Lo mismo hace `_safe_severidad` con `n/a`.

**Por qué importa:** un incidente real desaparece sin dejar rastro. Es un falso
negativo que se oculta a sí mismo, y contamina las dos categorías más pesadas
(30% tareas correctas, 10% fiabilidad). El contrato del repo lo prohíbe
explícitamente: *"un `tipo` fuera de los 8 es un error, no un valor que se
normaliza"* (`docs/architecture/contratos-agentes.md`).

**Cómo resolverlo:** que el valor inválido levante error y se reintente una vez
devolviéndole al modelo el error concreto ("`categoria` debe ser una de: …;
recibido: `otro`"). Si el reintento tampoco valida, marcar la señal como
`fallida` y **declararlo** — no convertirla en ruido.

---

## 4. La correlación cross-canal falla en el caso más común

**Estado:** `agent/correlate.py:46` exige **misma categoría** para considerar
dos señales el mismo incidente.

**Por qué importa:** el mismo corte entra como `indisponibilidad` por monitoring
y como `degradacion` por el dev chat todo el tiempo — son categorías vecinas y
`docs/taxonomia_incidentes.md` ya advierte que el clasificador las confunde. En
ese caso no deduplica y se reportan dos incidentes donde hay uno. Justo el
escenario que la demo quiere lucir.

**Cómo resolverlo:** relajar la condición — mismo servicio + ventana de tiempo
debería bastar para marcar *candidato a duplicado*, dejando la categoría como
señal de confianza y no como requisito. Alternativa más barata: agrupar las
categorías vecinas (`indisponibilidad`/`degradacion`, `datos`/`error_funcional`)
en familias y comparar por familia.

---

## 5. Sin manejo de fallos de la API

**Estado:** `agent/maas_client.py` no distingue 401, 429 ni timeout, y no
reintenta. `demo/live_server.py:405` sí atrapa la excepción y emite un evento
`agent_error`, así que la demo no se cae — pero no se recupera ni explica qué
pasó.

**Por qué importa:** es el 10% de "gestión de fallos", que hoy vale cero. Y la
inferencia corre en Hong Kong: la latencia desde Chile es real y un timeout en
vivo es un escenario probable, no teórico.

**Cómo resolverlo:** un reintento con backoff para 429/timeout, y mensajes
distintos por causa (clave inválida vs. saldo agotado vs. red). Un fallo
declarado con su causa puntúa; un stacktrace en pantalla, no.

---

## 6. Hay dos sistemas paralelos que resuelven lo mismo

**Estado:** conviven en el repo:

- **este proyecto** (`projects/devchat-generator/`): agente único, taxonomía en
  snake_case (`error_funcional`), KB y esquema propios.
- **el flujo multiagente** (`src/maas_demo/orchestrator.py` +
  `projects/bus-incidentes/` + `projects/agente-puente/`): triage → despacho →
  especialistas → consolidación, taxonomía en kebab-case (`error-funcional`),
  validación de contratos y compuerta de aprobación.

**Por qué importa:** hoy no se pueden conectar sin traducir la taxonomía, y
**alguien tiene que elegir cuál va al pitch**. Mostrar los dos confunde; mostrar
uno y que el otro quede muerto en el repo también resta.

**Recomendación:** el multiagente cubre mejor la rúbrica (orquestación 15%,
aprobación humana, contratos validados) y ya tiene tests. Este proyecto aporta
los generadores de los tres canales, que el otro no tiene. Lo natural es
quedarse con el multiagente como motor y con estos generadores como fuente de
señal — que es exactamente lo que hace `projects/agente-puente/`.

---

## 7. El canal de email no está desplegado

**Estado:** `projects/incident-agent/` tiene el pipeline
Postmark → Supabase escrito pero sin desplegar. Su propio README lista lo que
falta: `supabase link`, los secrets, el deploy de la Edge Function y pegar la
URL en el webhook de Postmark.

**Por qué importa:** menos que el resto. El generador sintético de email
(`channels/email/`) ya produce señal de ese canal, así que la demo funciona sin
el pipeline real. Es un "nice to have" de realismo, no un bloqueo.

---

## 8. Tool calling nativo: decisión pendiente

**Estado:** `agent/maas_client.py` tiene `chat_with_tools`, pero nadie lo llama.
Las "tools" son funciones Python orquestadas desde `loop.py`. Además, el
`CLAUDE.md` pedía *verificar tool calling en cada modelo antes del evento* y eso
nunca se hizo.

**Por qué importa:** son 15% de "uso de herramientas y orquestación". Orquestar
en código es **más confiable** que depender de que el modelo emita tool calls
bien formadas, y es defendible como decisión de diseño — pero hay que decidir si
se defiende así o se muestra tool calling real, y en ese caso verificar primero
qué modelos de MaaS lo soportan.

---

## Lo que sí está funcionando

- Los tres canales generan señal sintética con groundtruth separado de la señal.
- El bus reparte un mismo incidente a semáforo, logs y dev-chat de forma
  correlacionada, y cada canal degrada solo si otro se cae.
- El flujo multiagente valida contratos, aplica presupuesto y deja las acciones
  de riesgo esperando aprobación humana.
- El puente cierra el círculo y contrasta lo detectado contra la verdad.
- El feed del dev-chat exige token, como lo exigiría Slack de verdad.
