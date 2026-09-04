# Plan de mejora — cierre contra los criterios de evaluación

Escaneo: 2026-09-03. Stack levantado en `--mock` (8000/8001/8010/8028/8080) y una
instancia `live` aparte en 8081 para medir de verdad.

Contrastado contra **`origin/main` @ `946fffd`**, no contra el árbol local. Lo que
ya está resuelto arriba está marcado como tal y no vuelve a la lista.

---

## Qué se midió (no es opinión)

| Comprobación | Resultado |
| --- | --- |
| `python -m unittest discover -s tests` | **105 tests, OK** |
| Las 4 pantallas sirven | 8000 ✅ · 8001 ✅ · 8028 ✅ · 8080 ✅ |
| Flujo multiagente en `mock` (`/api/incidentes/run`) | completa, 3 llamadas, 11 ms |
| Corrida `live` #1 vía puente | **3/3 incidentes reales detectados**, tipo y severidad correctos, 4 hallazgos con confianza alta, `revertir_deploy` con `DEP-451` y `DEP-408` reales, 3 descartes correctos, reporte en las 5 secciones |
| Corrida `live` #2, mismo comando | **colgada >25 min sin una sola línea**, servidor sano todo el rato |
| `.env` con `MAAS_API_KEY` real en historial git | en `2014a19`, `04a3927`, `7832665`, `86aed46`, `c22aae7` |

La corrida #1 demuestra que **el agente funciona y funciona bien**. El trabajo que
queda es que eso se vea, se repita y se pueda puntuar.

## Ya resuelto en `origin/main` — no rehacer

- **UI del orquestador en `:8080`.** `app.js` ya llama a `/api/incidentes/run` y
  pinta fases, triage con evidencia y `motivo_ruteo`, especialistas en paralelo,
  hallazgos y cola de aprobación con botones. Era el hueco más caro y está cerrado.
- **Salida SARIF a code scanning** (`src/maas_demo/sarif.py`, ADR-0009) y la
  **corrida programada** (`.github/workflows/corrida-programada.yml`) con guarda
  de huso horario.
- `ejecutar-corrida.py` ampliado (+253 líneas) con la integración SARIF.

`orchestrator.py`, `provider.py` y `puente.py` **no han cambiado**: todo lo que
sigue apuntando a ellos sigue vigente.

---

## 1 · Tareas exitosas / correctas — 30 %

El bloque más pesado, y hoy no hay ninguna cifra que lo respalde.

### T1.1 — Convertir el contraste en un scorecard real
`projects/agente-puente/puente.py:153` (`contrastar`)

Compara **conjuntos de tipos**. Con eso, detectar 1 de 3 incidentes puede dar
"acertó" si el tipo coincide, y detectar 3 de 3 puede dar 0 si uno se llamó
distinto. Es la medición más pobre posible sobre el mejor activo del proyecto.

El bus ya entrega todo lo necesario y el agente nunca lo ve (`GET /api/verdad`):
`incidente_id`, `tipo`, `severidad`, `servicio`, `ruteo_defecto`,
`ataque_activo` y — clave — `accion_esperada`:

```json
"accion_esperada": {"action_id": "revertir_deploy", "params_clave": {"deploy_id": "DEP-451"}}
```

Reescribir `contrastar()` para emparejar por **servicio afectado + ventana
temporal** y emitir:

- `precision`, `recall`, `f1` sobre incidentes
- `exactitud_tipo`, `exactitud_severidad` (solo sobre los emparejados)
- `exactitud_ruteo` — ¿mandó al especialista que tocaba?
- `accion_correcta` — ¿`action_id` coincide con `accion_esperada` y los
  `params_clave` traen el identificador real?
- `falsos_positivos` — incidentes inventados que no existen en la verdad
- `descartes_correctos` — ruido que el bus marcó como no-incidente y el agente
  efectivamente descartó

**Aceptación:** `puente.py --json` devuelve un bloque `puntuacion` con esas 9
métricas y la sección 6 las imprime.

### T1.2 — Comando de puntuación repetible
Nuevo: `scripts/ejecutablesBase/puntuar.py`

```bash
python scripts/ejecutablesBase/puntuar.py --escenarios 8 --mode live --json-out evals/results/score.json
```

Provoca N escenarios del bus (hay 16), dispara una corrida por cada uno, agrega
las métricas de T1.1 y escupe una tabla. Ese archivo es la evidencia que se
enseña en la presentación.

**Aceptación:** una fila por escenario y una fila TOTAL. Si una corrida falla,
sale como fallo; nunca se promedia hacia fuera.

### T1.3 — `evaluar.py` no mide corrección
`scripts/ejecutablesBase/evaluar.py:47-52`

Los checks son `has_content`, `has_action` (¿aparece la palabra "Causa raíz"?),
`mode_visible`, `latency_visible`. Un modelo que devuelva las cinco cabeceras
vacías pasa. Y corre `ChatService` — una sola llamada —, **no el orquestador**:
el CI verde no dice nada sobre el agente que se demuestra.

Añadir un bloque `esperado` por caso en `evals/cases.json` (tipo, severidad,
`action_id`, identificador que debe citarse) y validar contra él. Cambiar el paso
de CI para que ejercite el orquestador.

**Aceptación:** el job `verificacion` corre el flujo multiagente en mock y falla
si la exactitud de tipo baja de un umbral declarado en el archivo.

### T1.4 — El `mock` "falla" delante del jurado
`src/maas_demo/provider.py:92` (`MockProvider`)

En mock el triage siempre devuelve un `INC-01 · degradacion · media` con
evidencia `"El volcado requiere investigación adicional"`. Contra 3 incidentes
reales, el contraste medido hoy fue: **0 acertados, 3 no detectados, 1
inventado**. Y mock es justo lo que el `README.md` propone para la demo de dos
minutos: quien la siga ve al agente errar todo.

Hacer el mock determinista **y correcto** para los escenarios del bus: reconocer
las marcas del volcado (`evento=deploy`, `metric=db.lock_wait_seconds`, `401`,
`disk=`) y devolver la clasificación que corresponde. Sigue sin llamar a la nube
y sigue marcándose `MOCK` en pantalla.

**Aceptación:** `puente.py` en mock, con 3 incidentes provocados, da recall 1.0 y
0 inventados. Los 105 tests siguen verdes.

---

## 2 · Comportamiento del agente y autonomía — 25 %

La pantalla ya está (ver *Ya resuelto*). Queda lo de abajo.

### T2.1 — Dos bugs de render en la pantalla nueva de `:8080` 🔴
`src/maas_demo/static/app.js` en `origin/main`

Ambos salen en pantalla, en la pantalla insignia, y los ve cualquiera:

**a) `app.js:124`** — `Descartado: ${finding.descartado.join(" · ")}`

`descartado` es una lista de **objetos** `{hipotesis, dato_que_la_descarta}`
(contrato en `orchestrator.py`, `_ESQUEMA_HALLAZGO`). `join()` sobre objetos
imprime `[object Object] · [object Object]`. Y justo ahí está lo que más peso
tiene para el criterio de alucinaciones: las hipótesis que el especialista
descartó y el dato con el que las descartó.

**b) `app.js:87`** — el formateador compartido de descartados y diferidos:

```js
const text = typeof item === "string" ? item : `${item.incidente_id}: ${item.motivo}`;
```

Los **diferidos** sí traen `incidente_id`. Los **descartados del triage** son
`{senal, motivo, evidencia}` — no tienen `incidente_id`. Resultado en pantalla:
`Descartado — undefined: <motivo>`.

Separar los dos formateadores y desplegar cada hipótesis descartada con su dato.

**Aceptación:** una corrida live en `:8080` sin un solo `undefined` ni
`[object Object]`, y las hipótesis descartadas legibles.

### T2.2 — Modo autónomo visible
`projects/devchat-generator/demo/live_server.py` (`_agent_enabled`)

Que el agente no arranque solo es correcto (ADR-0004), pero "autonomía" es el
25 % y el estado por defecto es `Agente: OFF` con los paneles vacíos.

Añadir modo vigilancia: con el toggle en ON el agente sondea
`/api/incidentes/activos`, dispara una corrida por cada incidente nuevo **sin que
nadie toque nada**, y lo único que espera humano es la aprobación de la acción.
En cabecera: `vigilando · N señales · última corrida hace Xs`.

**Aceptación:** se provoca un incidente por curl y, sin más intervención, aparece
en la cola de aprobaciones de `:8001` y `:8080`.

### T2.3 — Hay dos agentes distintos y no se parecen
`src/maas_demo/orchestrator.py` vs `projects/devchat-generator/agent/loop.py`

- `orchestrator.py`: multiagente, taxonomía cerrada de 8 tipos, catálogo de 10
  acciones, compuerta de aprobación. Alimenta `:8080` y el puente.
- `agent/loop.py`: un solo loop `classify → RAG → consolidate`, enum `Categoria`
  propio, sin acciones. Alimenta `:8001`.

Dos taxonomías y dos contratos en la misma demo. `sarif.py` ya hizo lo correcto
—importar `TYPES` de `orchestrator` para no duplicar la taxonomía—; aplicar el
mismo criterio a `loop.py`. Y declarar en `docs/architecture/flujo-agentes.md`
cuál es cuál y por qué conviven.

**Aceptación:** una señal clasificada en `:8001` y la misma en `:8080` usan el
mismo vocabulario de tipos.

---

## 3 · Uso de herramientas y orquestación — 15 %

### T3.1 — Los especialistas no usan herramientas
`src/maas_demo/orchestrator.py` (`SPECIALIST_PROMPTS`, `execute`)

Reciben un JSON y devuelven un JSON. No consultan nada. "Uso de herramientas" es
el 15 % y la única herramienta real del sistema es la KB del *otro* agente
(`projects/devchat-generator/agent/kb.py`), que el orquestador no toca.

Dar a los especialistas 3 tools de solo lectura, coherentes con la invariante de
que este agente no ejecuta:

- `buscar_incidente_previo(texto)` → `kb.py`, ya existe, sin LLM
- `pedir_lineas(servicio, desde, hasta)` → `GET :8010/api/feed/monitoreo`
- `estado_servicio(nombre)` → `GET :8028/api/metrics`

Emitir un evento SSE `herramienta` por llamada y pintarlo en la línea de tiempo
que `app.js` ya tiene montada.

**Aceptación:** en una corrida live al menos un especialista consulta la KB y el
hallazgo cita el incidente previo encontrado.

### T3.2 — Pintar las trazas que ya se recogen
`orchestrator.py` (`Trace`, `result["trazas"]`)

Se registran fase, origen, ms y estado por llamada, se persisten en Supabase y no
se muestran en ninguna pantalla — `app.js` de `origin/main` tampoco las consume.
Añadir un desplegable "traza de la corrida" al final del reporte.

### T3.3 — No prometer routing de modelos
`src/maas_demo/config.py:56-58`

`MAAS_MODELO_TRIAGE` / `_ESPECIALISTA` / `_CONSOLIDACION` existen, pero solo
`glm-5.2` está habilitado (el resto da 403). El mecanismo está y no se puede
demostrar. `DEMO.md` ya avisa de no afirmarlo; que `README.md` y
`docs/architecture/stack.md` digan lo mismo: **capacidad implementada, no
demostrable con la cuota actual**. Sobrevender esto es lo que un jurado técnico
castiga.

---

## 4 · Gestión de ambigüedad y fallos — 10 %

### T4.1 — Una corrida `live` no tiene techo ⚠
`src/maas_demo/provider.py:176`

```python
with self.opener(request, timeout=self.timeout_seconds) as response:
```

En `urlopen`, `timeout` es el tiempo máximo **entre lecturas del socket**, no un
plazo total. Con SSE, mientras el proveedor mande un byte cada menos de 180 s la
llamada no vence nunca. `MAAS_TIMEOUT_SECONDS=180` no acota una corrida: acota un
trozo.

Medido hoy: la corrida #1 terminó bien; la #2, idéntica, **estuvo >25 minutos sin
emitir una línea** con el servidor sano. Si eso pasa en el escenario, se acabó la
demo. `DEMO.md` promete ~2,5 min.

Arreglo:
1. Plazo de reloj por llamada dentro del bucle de `stream()`: al pasarse, cortar
   y lanzar `ProviderError` diciendo cuánto esperó.
2. Presupuesto total de corrida (p. ej. 150 s) en `Orchestrator.stream`: al
   agotarse, emitir `fase: presupuesto_agotado` y **entregar lo que haya** —
   triage sí, especialistas parciales — con `status: "parcial"`.
3. Barra de presupuesto en `:8080`, junto a la línea de fases que ya existe.

**Aceptación:** con un proveedor simulado que gotea un byte cada 30 s, la corrida
termina dentro del presupuesto declarado y devuelve resultado parcial, no un
cuelgue.

### T4.2 — Los especialistas no reintentan
`orchestrator.py` (`execute`)

El triage sí reintenta una vez devolviendo el error de validación concreto. Un
especialista falla y queda `estado: "fallido"` a la primera. Aplicarle la misma
política.

**Aceptación:** un test con un proveedor que devuelve JSON inválido la primera vez
y válido la segunda produce un hallazgo completado.

### T4.3 — Canal caído: se maneja pero no se ve
`puente.py:66` lo declara bien (`canales_caidos`). Ninguna pantalla lo dice.
Llevarlo a la cabecera de `:8080` y `:8001`: `monitoreo ✅ · dev-chat ✅ · logs ✖
no disponible`.

---

## 5 · Fiabilidad y prevención de alucinaciones — 10 %

### T5.1 — La evidencia citada no se verifica ⚠ mejor coste/impacto del plan
`orchestrator.py` (`validate_triage`, `validate_finding`)

Se valida que `evidencia` sea una lista de 1 a 5 (o 1 a 8) strings. **No se
comprueba que esas líneas existan en el volcado.** El modelo puede parafrasear,
resumir o inventar una línea y pasa la validación entera.

Añadir anclaje literal: cada string de `evidencia` debe aparecer en el volcado de
entrada (normalizando espacios, o por prefijo con umbral). Lo que no ancla se
marca `evidencia_no_verificada` y baja la confianza del hallazgo.

Y enseñarlo: en las tarjetas que `app.js` ya pinta, cada línea con **✓ verificada
contra el volcado**. Es el artefacto anti-alucinación más convincente que se
puede poner en pantalla, y sale de un `in` sobre un string.

**Aceptación:** un test con un hallazgo cuya evidencia no está en el volcado lo
marca como no verificado y no le deja proponer acción.

### T5.2 — Los identificadores de las acciones no se anclan
`orchestrator.py` (`validate_finding`)

Se valida que `action_id` esté en el catálogo cerrado y que `params` sea un
objeto. **El contenido de `params` no se valida.** El prompt dice "Nunca inventes
identificadores: usa los que aparecen literalmente en la evidencia" y nada lo hace
cumplir: `revertir_deploy` con un `deploy_id` inventado entra a la cola igual.

Validar que cada valor de `params` con pinta de identificador (`DEP-451`,
`10.0.0.9`, `TRX-4471`, `svc-cache`) aparezca literalmente en la evidencia citada.
Si no, la acción se descarta y se declara por qué.

**Aceptación:** un hallazgo con `deploy_id: "DEP-999"` inexistente no llega a la
cola de aprobación y el motivo sale en la traza.

### T5.3 — La API key está en el historial de git 🔴
`.env` aparece en `2014a19`, `04a3927`, `7832665`, `86aed46`, `c22aae7`.

Hoy está en `.gitignore` (líneas 9-11) y ya no se versiona, pero el repositorio
es público y **la clave sigue siendo recuperable de cualquiera de esos commits**.

1. **Rotar `MAAS_API_KEY` ya** — es lo único que cierra el agujero de verdad.
2. Rotar también `HW_ACCESS_KEY` / `HW_SECRET_KEY`.
3. Purgar el historial (`git filter-repo`) o, si no se puede coordinar con las 6
   ramas abiertas, dejarlo documentado y asumido tras la rotación.

No es puntuación de hackathon: es una credencial viva en un repo público.

---

## 6 · Experiencia de usuario y calidad de la demo — 5 %

Cuatro bugs visibles en las capturas. Baratos, y los ve cualquiera.

### T6.1 — Todo el dashboard dice `unhealthy` con las barras en verde
`projects/devchat-generator/demo/live_server.py:346`

```python
_monitoring_metrics[servicio]["health"] = "unhealthy"
```

Se marca `unhealthy` ante **cualquier** alerta `firing` y solo se limpia si llega
una `resolved` del mismo servicio. Como las firing dominan, en un minuto los 6
servicios están en rojo mientras sus números siguen en los valores sanos por
defecto (250 ms, 1,0 %, 45 %). En la captura: insignia roja `unhealthy` junto a
tres barras verdes, en los seis.

Derivar `health` de las métricas mostradas, no de un flag pegajoso: `unhealthy`
si `latency > 800` o `error_rate > 0.05` o `disk > 85`.

### T6.2 — Hueco negro en la mitad inferior de `:8001`
`projects/devchat-generator/demo/static/live.html:84-86`

`.main-bottom` es un flex con tres hijos de base fija: `240 + 280 + 280 = 800 px`.
A 1500 px de ancho quedan 700 px de vacío negro a la derecha. `flex: 1` en el
último panel, o pasar `.main-bottom` a grid `240px 1fr 1fr`.

### T6.3 — La insignia de estado del semáforo sale en blanco
`projects/Metricas(polling)/index.html:107`

```html
<span class="... bg-current text-white mix-blend-overlay">${metrics.status}</span>
```

`bg-current` pinta el fondo del mismo color que el texto y `mix-blend-overlay`
remata: el `OPERATIONAL` / `DEGRADED` / `OUTAGE` es invisible. En la captura, cuatro
píldoras vacías. Usar la clase de color que `getStatusColor()` ya calcula.

### T6.4 — Dev Chat y Email arrancan vacíos en `:8001`
Los paneles solo se llenan según van disparando los generadores: al abrir, dos de
cuatro columnas están en blanco. Sembrar con las últimas 20 entradas de
`channels/*/data/*.jsonl` al conectar el WebSocket.

### T6.5 — `docs/product/demo.md` contradice a `DEMO.md`
Sigue describiendo el guion de 3 minutos del chat de una sola llamada
("Introducir un reto", "señalar el streaming"). El guion vigente es el `DEMO.md`
de la raíz, con 5 servicios y 7 pasos. Reescribirlo, o borrarlo y dejar el puntero.

### T6.6 — `:8000` se queda en "conectando…"
`channels/devchat/live_simulator/static/index.html:130` — el estado inicial solo
cambia en `ws.onopen`. Pintar "en vivo" en cuanto llegue el primer mensaje.

---

## 7 · Creatividad — 5 %

### T7.1 — Poner el marcador ciego en pantalla
Lo más original del proyecto ya está construido y **solo se ve en una terminal**:
el bus guarda la verdad, el agente nunca la ve, y al final se contrasta. Eso es
exactamente lo que separa clasificar bien de generar texto plausible, y no suele
traerlo nadie.

Añadir a `:8080` un panel **Marcador** que aparezca *después* del reporte, con las
métricas de T1.1 y la frase "el agente no vio estos datos". Que se destape delante
del jurado.

### T7.2 — El rango de refuerzo, en 30 segundos grabados
`reinforcement-range/` es el contraste fuerte del pitch: el Agente 1 diagnostica
sin tocar nada, el Agente 2 edita código en un contenedor y lo reinicia de verdad.
Hoy es el paso 7 de `DEMO.md`, opcional y con Docker por delante.

Grabar un clip de 30 s (ataque → el agente refuerza → el ataque rebota) y
enlazarlo desde el `README.md`. Un vídeo siempre corre; Docker en el escenario, no.

---

## Orden de ejecución

Si solo entra una cosa, es **T4.1**: es lo único de esta lista que puede tumbar la
demo en vivo. Si entran cuatro, T4.1 + T2.1 + T5.1 + T5.2.

| # | Tarea | Criterio | Peso | Esfuerzo |
| --- | --- | --- | --- | --- |
| 1 | **T4.1** Plazo de reloj y presupuesto de corrida | Fallos | 10 % | medio |
| 2 | **T2.1** Los 2 bugs de render de `:8080` | Autonomía | 25 % | bajo |
| 3 | **T5.1** Evidencia verificada + sello ✓ | Alucinaciones | 10 % | bajo |
| 4 | **T5.2** Identificadores anclados | Alucinaciones | 10 % | bajo |
| 5 | **T1.1** Scorecard real | Corrección | 30 % | medio |
| 6 | **T6.1–T6.4** Los 4 bugs visuales | UX | 5 % | bajo |
| 7 | **T1.4** Mock determinista y correcto | Corrección | 30 % | medio |
| 8 | **T1.2** `puntuar.py` | Corrección | 30 % | medio |
| 9 | **T7.1** Marcador en pantalla | Creatividad | 5 % | bajo |
| 10 | **T3.1** Tools de solo lectura | Herramientas | 15 % | alto |
| 11 | **T2.2** Modo vigilancia | Autonomía | 25 % | medio |
| 12 | **T3.2** Trazas visibles | Herramientas | 15 % | bajo |
| 13 | **T4.2** Reintento de especialistas | Fallos | 10 % | bajo |
| 14 | **T1.3** CI que mida el orquestador | Corrección | 30 % | medio |
| 15 | **T2.3** Unificar taxonomías | Autonomía | 25 % | medio |
| 16 | **T6.5, T3.3** Docs sin contradicciones ni promesas | UX | 5 % | bajo |
| 17 | **T7.2** Clip del rango de refuerzo | Creatividad | 5 % | medio |

**Fuera de la tabla y antes que todo: T5.3, rotar las credenciales.** No suma
puntos; evita un problema real.

## Invariantes que ninguna tarea puede romper

De `AGENTS.md`, siguen valiendo:

- `mock` y `live` siempre visibles. Un fallo `live` nunca se convierte en éxito
  `mock` silencioso.
- `MAAS_API_KEY` solo en backend. Nunca al navegador, nunca al repo.
- El dominio depende del contrato `ChatProvider`, no de URLs de Huawei.
- El Agente 1 es de solo lectura. Las acciones se proponen y esperan a un humano
  (ADR-0004). El único que ejecuta es el rango de refuerzo, y está aislado.
- Los 105 tests siguen en verde al final de cada tarea.
