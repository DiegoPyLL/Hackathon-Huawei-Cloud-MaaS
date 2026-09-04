# Backlog nocturno

Cola cerrada y ordenada. Se toma **la primera sin marcar**. Reglas en
[`PROTOCOLO.md`](PROTOCOLO.md).

Estados: `- [ ]` pendiente · `- [x]` hecha · `- [!]` bloqueada.

El orden es por retorno sobre la ponderación del jurado, no por comodidad. Las
primeras cuatro desbloquean el resto: mientras el presupuesto corte antes de los
especialistas, la conversión medida es 0 % y ninguna mejora posterior se puede
demostrar.

---

## Bloque 1 — Desbloquear la medición

- [x] **N-01 · Subir el presupuesto de corrida a 300 s**
  `src/maas_demo/orchestrator.py` (`PRESUPUESTO_CORRIDA_SEG`), `src/maas_demo/static/app.js` (`BUDGET_SECONDS`).
  Medido: una corrida live con 3 incidentes consumió 172 s solo en triage y los
  3 se perdieron con `Presupuesto de corrida agotado antes de despachar
  especialistas`. El presupuesto arregló el cuelgue de 25 min pero quedó por
  debajo del coste real, así que ahora toda corrida live termina parcial y sin
  reporte ejecutivo.
  **Aceptación:** la constante es 300, `BUDGET_SECONDS` en el front vale lo mismo
  (no lo hardcodees dos veces sin un comentario que lo diga), y hay un test que
  fija que el front y el back declaran el mismo presupuesto o que el front lo
  lee de `/api/health`.

- [ ] **N-02 · Corrida live de control, una sola vez**
  Sin cambios de código. **Única excepción a la prohibición de `live`.**
  Levantá el stack (`python projects/bus-incidentes/levantar_todo.py`), provocá
  3 escenarios distintos, dispará una corrida por el puente y guardá la salida
  en `evals/results/corrida-noche.json` (`puente.py --json`).
  **Aceptación:** el archivo existe, la corrida terminó `completada` (no
  `parcial`) y la bitácora anota la latencia real y la conversión que dio
  `:8020`. Si sale `parcial` otra vez, anotá el motivo y seguí — no subas más
  el presupuesto por tu cuenta.

- [ ] **N-03 · `contrastar()` delega en la trazabilidad**
  `projects/agente-puente/puente.py` (`contrastar`), `projects/agente-puente/trazabilidad.py`.
  `contrastar()` sigue comparando **conjuntos de tipos**: acertar el tipo de otro
  incidente cuenta como acierto y detectar el correcto con otro nombre cuenta
  como fallo. `trazabilidad.py` ya resuelve esto bien, por evidencia anclada.
  **Aceptación:** `contrastar()` devuelve además `precision`, `recall`, `f1`,
  `exactitud_tipo`, `exactitud_severidad`, `exactitud_ruteo` y `accion_correcta`
  calculados desde el linaje. La sección 6 del CLI las imprime. Tests nuevos.

- [ ] **N-04 · `puntuar.py` — puntuación repetible sobre varios escenarios**
  Nuevo: `scripts/ejecutablesBase/puntuar.py`.
  ```
  python scripts/ejecutablesBase/puntuar.py --escenarios 6 --mode mock --json-out evals/results/score.json
  ```
  Provoca N escenarios del bus (hay 16), dispara una corrida por cada uno, agrega
  las métricas de N-03 y escupe una tabla: una fila por escenario y una TOTAL.
  **Aceptación:** corre entero en `mock` sin tocar la nube. Una corrida fallida
  sale como fallo y no se promedia hacia fuera. Test con un bus simulado.

---

## Bloque 2 — Fiabilidad y anti-alucinación

- [ ] **N-05 · Anclar también la evidencia del triage**
  `src/maas_demo/orchestrator.py` (`validate_triage`).
  El anclaje literal se aplicó a `validate_finding` pero **no** a
  `validate_triage`, así que las tarjetas de incidentes detectados en `:8080` no
  llevan sello y la mitad de la evidencia que se muestra no está verificada.
  **Aceptación:** `validate_triage` recibe el volcado y marca
  `evidencia_verificada` por incidente igual que los hallazgos; `app.js` pinta
  el sello también ahí. Tests.

- [ ] **N-06 · Ampliar el patrón de identificadores**
  `src/maas_demo/orchestrator.py` (`_PATRON_IDENTIFICADOR`).
  Es sensible a mayúsculas y deja huecos: `HOST-12` no matchea contra
  `host-[a-z0-9-]+`, y no cubre formatos que sí aparecen en los escenarios
  (`PED-88304`, `CRED-2071`, `AS20473`, `SES-…`).
  **Aceptación:** patrón case-insensitive y con los formatos que aparecen de
  verdad en `projects/monitoreo/generator/`. Un test por formato. Ojo: sub-detectar
  es preferible a sobre-detectar, así que no metas patrones tan amplios que
  empiecen a marcar palabras normales.

- [ ] **N-07 · Decidir el umbral de anclaje de acciones**
  `src/maas_demo/orchestrator.py` (`validate_finding`).
  Hoy la acción se anula solo si **toda** la evidencia falla el anclaje
  (`len(no_verificadas) == len(anclaje)`). Si el especialista cita 3 líneas y se
  inventa 1, la acción pasa igual.
  **Aceptación:** la acción se anula si **alguna** cita no ancla, salvo que la
  cita no anclada sea irrelevante para los `params` propuestos. Documentá la
  decisión en el docstring: es un criterio, no una obviedad, y tiene que quedar
  por escrito por qué se eligió.

- [ ] **N-08 · Reintento de especialistas**
  `src/maas_demo/orchestrator.py` (`execute`).
  El triage reintenta una vez devolviendo el error de validación concreto; un
  especialista falla y queda `fallido` a la primera.
  **Aceptación:** misma política de un reintento. Test con un proveedor que
  devuelve JSON inválido la primera vez y válido la segunda.

---

## Bloque 3 — Los bugs visibles (baratos, los ve cualquiera)

- [ ] **N-09 · El dashboard dice `unhealthy` con las barras en verde**
  `projects/devchat-generator/demo/live_server.py:345`.
  `health` se marca `unhealthy` ante cualquier alerta `firing` y solo se limpia
  con una `resolved` del mismo servicio. Como las firing dominan, en un minuto
  todo está en rojo con los números sanos por defecto al lado.
  **Aceptación:** `health` se deriva de las métricas mostradas — `unhealthy` si
  `latency > 800` o `error_rate > 0.05` o `disk > 85`. Test de la función.

- [ ] **N-10 · Hueco negro en la mitad inferior de `:8001`**
  `projects/devchat-generator/demo/static/live.html:79-84`.
  `.main-bottom` es un flex con tres hijos de base fija (`240 + 280 + 280 =
  800px`); a 1500px de ancho quedan 700px de vacío negro.
  **Aceptación:** el último panel se estira (`flex: 1`) o `.main-bottom` pasa a
  grid `240px 1fr 1fr`. Verificalo con una captura headless de Chrome a
  1500x1500 y anotá en la bitácora que no queda vacío.

- [ ] **N-11 · La píldora de estado del semáforo sale en blanco**
  `projects/Metricas(polling)/index.html:107`.
  `bg-current text-white mix-blend-overlay` pinta el fondo del mismo color que
  el texto: `OPERATIONAL`/`DEGRADED`/`OUTAGE` es invisible.
  **Aceptación:** usa la clase que `getStatusColor()` ya calcula. Captura
  headless que muestre el texto legible.

- [ ] **N-12 · Dev Chat y Email arrancan vacíos en `:8001`**
  `projects/devchat-generator/demo/live_server.py`, `static/live.html`.
  Los paneles solo se llenan cuando disparan los generadores: al abrir, dos de
  cuatro columnas están en blanco.
  **Aceptación:** al conectar el WebSocket se siembran las últimas ~20 entradas
  de `channels/*/data/*.jsonl`. Marcadas visualmente como historial, no como
  señal nueva — si no, contaminan las estadísticas.

- [ ] **N-13 · `:8000` se queda en "conectando…"**
  `projects/devchat-generator/channels/devchat/live_simulator/static/index.html:130`.
  El estado inicial solo cambia en `ws.onopen`.
  **Aceptación:** pasa a "en vivo" también cuando llega el primer mensaje.

---

## Bloque 4 — Corrección del agente

- [ ] **N-14 · Mock determinista y correcto**
  `src/maas_demo/provider.py` (`MockProvider`).
  En mock el triage siempre devuelve `INC-01 · degradacion · media` con evidencia
  `"El volcado requiere investigación adicional"`. Medido contra 3 incidentes
  reales: 0 acertados, 3 no detectados, 1 inventado. Y mock es lo que el README
  propone para la demo de dos minutos.
  **Aceptación:** el mock reconoce las marcas del volcado (`evento=deploy`,
  `metric=db.lock_wait_seconds`, `401`, `disk=`, `secret_scan`) y devuelve la
  clasificación que corresponde, citando líneas **literales del volcado** (si no,
  N-05 las marcará como no verificadas). Sigue sin llamar a la nube y sigue
  marcándose `MOCK`. Con 3 incidentes provocados, recall 1.0 y 0 inventados.

- [ ] **N-15 · Bajar los falsos positivos del triage**
  `src/maas_demo/orchestrator.py` (`TRIAGE_PROMPT`).
  Medido: el agente inventó un `INC-04` a partir de charla de phishing del
  dev-chat que no corresponde a ningún incidente del bus. Precisión 75 %.
  **Aceptación:** el prompt exige que **toda** evidencia citada sea una línea
  textual del volcado y que una conversación sin alerta ni métrica asociada vaya
  a `descartados`, no a `incidentes`. Verificalo con `puntuar.py` de N-04 en mock:
  la precisión no puede bajar respecto de la medición anterior.

- [ ] **N-16 · Canal caído visible en pantalla**
  `src/maas_demo/static/app.js`, `projects/devchat-generator/demo/static/live.html`.
  `puente.py` ya declara `canales_caidos` y ninguna pantalla lo muestra.
  **Aceptación:** cabecera con `monitoreo ✓ · dev-chat ✓ · logs ✗ no disponible`.

- [ ] **N-17 · Trazas de la corrida visibles**
  `src/maas_demo/orchestrator.py` (ya las recoge en `result["trazas"]`), `app.js`.
  Se registran fase, origen, ms y estado por llamada, se persisten en Supabase y
  no se muestran en ninguna pantalla.
  **Aceptación:** desplegable "traza de la corrida" al final del reporte en
  `:8080`, con la tabla de fases y milisegundos.

---

## Bloque 5 — Lo grande (solo si llegaste hasta acá)

- [ ] **N-18 · Herramientas de solo lectura para los especialistas**
  `src/maas_demo/orchestrator.py`.
  Hoy reciben un JSON y devuelven un JSON; no consultan nada. "Uso de
  herramientas" pesa 15 % y la única herramienta real del sistema es la KB del
  otro agente (`projects/devchat-generator/agent/kb.py`), que el orquestador no
  toca.
  **Aceptación:** tres tools de solo lectura — `buscar_incidente_previo(texto)`
  contra `kb.py`, `pedir_lineas(servicio)` contra `:8010/api/feed/monitoreo`,
  `estado_servicio(nombre)` contra `:8028/api/metrics` — y un evento SSE
  `herramienta` por llamada, pintado en la línea de tiempo. **No rompas la
  invariante de solo-lectura.** Si esto se pone grande, partilo: primero la KB
  sola, y anotá las otras dos como tareas nuevas.

- [ ] **N-19 · Unificar la taxonomía de los dos agentes**
  `projects/devchat-generator/agent/schema.py` y `loop.py` vs `src/maas_demo/orchestrator.py`.
  `orchestrator.py` usa los 8 tipos canónicos; `loop.py` tiene su propio enum
  `Categoria`. Dos vocabularios en la misma demo. `sarif.py` ya hizo lo correcto
  importando `TYPES` de `orchestrator`; aplicá el mismo criterio.
  **Aceptación:** una señal clasificada en `:8001` y la misma en `:8080` usan el
  mismo vocabulario. Ojo con los datasets versionados: si tienen la taxonomía
  vieja, hay que migrarlos o mapearlos, y eso puede volver la tarea grande. Si
  se pone grande, BLOQUEADA con la explicación.

- [ ] **N-20 · Documentación que no se contradice**
  `docs/product/demo.md`, `README.md`, `docs/architecture/stack.md`.
  `docs/product/demo.md` sigue describiendo el guion de 3 minutos del chat de
  una sola llamada, que ya no existe; el vigente es `DEMO.md` de la raíz.
  Además, `README.md` no menciona `:8020` ni el routing de modelos como lo que
  es: implementado pero **no demostrable**, porque solo `glm-5.2` está habilitado
  (los demás dan 403).
  **Aceptación:** `docs/product/demo.md` reescrito o borrado con un puntero;
  `README.md` con las 6 pantallas y sin prometer routing.

- [ ] **N-21 · CI que mida el orquestador, no `ChatService`**
  `.github/workflows/ci.yml`, `scripts/ejecutablesBase/evaluar.py`, `evals/cases.json`.
  `evaluar.py` solo comprueba que aparezcan las cabeceras ("¿está la palabra
  *Causa raíz*?") y corre `ChatService`, una sola llamada — no el orquestador. El
  CI verde no dice nada sobre el agente que se demuestra.
  **Aceptación:** bloque `esperado` por caso (tipo, severidad, `action_id`,
  identificador que debe citarse) y el job corriendo el flujo multiagente en
  mock, fallando si la exactitud de tipo baja de un umbral declarado en el archivo.

---

## Encontradas durante la noche

Anotá acá lo que descubras y no corresponda a la tarea en curso. **No las hagas
en el momento**: se hacen cuando la cola llegue a ellas.

<!-- nuevas tareas al final de esta sección -->
