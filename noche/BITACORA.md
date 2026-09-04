# Bitácora nocturna

Una entrada por vuelta del bucle. Esto es lo que se lee a las 7am para saber qué
pasó sin tener que leer 40 commits.

Formato en [`PROTOCOLO.md`](PROTOCOLO.md).

---

## Punto de partida
Estado inicial antes de arrancar el bucle:

- Rama base: `trazabilidad-conversion`
- Tests: 159 en verde
- Compuerta: verde
- Conversión medida en `:8020` con 3 incidentes live: 100% hasta ruteo,
  0% a diagnóstico (los 3 perdidos en el salto al especialista por el
  presupuesto de 150s). Precisión 75% — 1 falso positivo de 4 detecciones.
- Backlog: 21 tareas, ninguna empezada.

---

## N-01 · Subir el presupuesto de corrida a 300 s · 00:01
Estado: HECHA
Commit: 2ad6925
Qué cambió: PRESUPUESTO_CORRIDA_SEG 150→300; /api/health expone presupuesto_seg; app.js lo lee de ahí (fallback 300).
Verificación: compuerta verde, 160 tests (+1).
Nota: el front ya no hardcodea el presupuesto; lo toma de /api/health.

## N-02 · Corrida live de control, una sola vez · 01:12
Estado: HECHA (parcial)
Commit: 854f0be
Qué cambió: sin cambios de código. Guardado evals/results/corrida-noche.json.
Verificación: compuerta verde, 160 tests.
Nota: stack live, 3 escenarios (caida_tras_deploy, bloqueo_cuenta_masivo,
disco_motor_datos). La corrida terminó PARCIAL: latency 150012ms, presupuesto
agotado, 0 fallidos, 2 diferidos. Conversión global 0.0 — los 2 incidentes
detectados no llegaron a diagnosticados porque el presupuesto se agotó antes
de despachar especialistas. No subí más el presupuesto por mi cuenta. La
latencia real sugiere que el cuello sigue en el triage (8 llamadas en 150s).

## R-11 · Plazo por llamada acotado al presupuesto · 04:35
Estado: HECHA
Commit: be2fae5
Autor: relevo (Claude) — SIN REVISIÓN INDEPENDIENTE
Qué cambió: el plazo efectivo de cada llamada es min(timeout, presupuesto
restante); un fallo de triage produce un `done` con status "fallida", motivo y
trazas en vez de una excepción que escapa.
Verificación: compuerta verde, 163 tests (+3). Validado además contra live: la
corrida ya no se evapora, devuelve `done` consultable.
Nota: se adaptó la firma de tres dobles `_provider` en tests existentes. Sus
aserciones no se tocaron.

## N-02 · Corrida live de control · 04:42
Estado: BLOQUEADA
Autor: relevo (Claude) — SIN REVISIÓN INDEPENDIENTE
Motivo: el triage live no llega a entregar. Dos corridas reales con el
presupuesto ya en 300s y `/api/health` verificado (`presupuesto_seg: 300.0`):
  1ª — plazo de reloj de 180s agotado en el triage, corrida perdida entera.
  2ª — con R-11 puesto: `done` limpio con status "fallida" a los 144s, motivo
       "Expecting property name enclosed in double quotes: line 3 column 2".
La segunda no es un timeout: el modelo devolvió JSON malformado. Y ese caso NO
tiene reintento (ver R-12). Estaba marcada [x] por error; se desmarcó.
Embudo en ambas: 4/4 recogidos → 0/4 detectados, todo perdido en triage.

## R-12 · Reintento del triage cubre el JSON malformado · 05:10
Estado: HECHA
Commit: 8357f63
Autor: relevo (Claude) — SIN REVISIÓN INDEPENDIENTE
Qué cambió: se pide el texto crudo y se parsea aparte, así el mismo reintento
cubre JSON que no parsea y JSON que parsea pero no valida.
Verificación: compuerta verde, 165 tests (+2). Validado contra live: la corrida
pasó de morir en triage a conversión 0.75.

## R-13 · La consolidación ya no tira la corrida · 05:22
Estado: HECHA
Commit: (este)
Autor: relevo (Claude) — SIN REVISIÓN INDEPENDIENTE
Qué cambió: un fallo de consolidación deja la corrida en `parcial` con los
hallazgos y las acciones conservados, en vez de perder el `done` entero.
Verificación: compuerta verde, 166 tests (+1). Falta validar contra live.
Nota: R-11 había protegido el triage pero no el patrón; esto lo completa.

## N-02 · Corrida live de control — progreso, sigue BLOQUEADA · 05:22
Estado: BLOQUEADA
Autor: relevo (Claude) — SIN REVISIÓN INDEPENDIENTE
Tercera corrida live (con R-12): el pipeline se desbloqueó de verdad.
  embudo   4/4 recogidos → 3/4 detectados → 3/4 tipo ok → 3/4 ruteo ok
           → 3/4 diagnosticados → 1/4 con acción
  conversión 0.75 (venía de 0.0) · precisión 1.0 · 0 falsos positivos
  4 descartes declarados · 4 hallazgos · 1 acción en cola
Pero no llegó el `done`: la consolidación venció con 41.8s restantes y su
excepción escapó. Eso es lo que arregla R-13. Falta una cuarta corrida para
cerrar N-02; no se hizo en este tick por lo largo que venía.

## N-02 · Corrida live de control · 06:20
Estado: HECHA (parcial, motivo declarado)
Commit: (el anterior a este)
Autor: relevo (Claude) — SIN REVISIÓN INDEPENDIENTE
Qué cambió: sin código. Regenerado evals/results/corrida-noche.json con una
corrida válida — `presupuesto_seg: 300.0` verificado en /api/health ANTES de
correr, que es lo que faltó la primera vez (R-05/R-07).
Verificación: compuerta verde, 166 tests. R-13 confirmado contra live: llegó el
`done` en vez de perderse la corrida al agotarse el presupuesto.
Resultado: status parcial, 300009ms, 4/4 detectados, 3/4 tipo correcto, 4/4
ruteo correcto, 1/4 diagnosticados. Conversión 0.25, precisión 1.0, 0 falsos
positivos, 5 descartes declarados.
Nota: termina `parcial` y no `completada`. El criterio de N-02 previa ese caso
("si sale parcial otra vez, anotá el motivo y seguí"). El motivo está medido en
las trazas y va como R-14: el triage consume 170.7s de los 300 en UNA llamada,
así que a los especialistas les quedan ~130s y a la consolidación nada.
Trazas: triage 170668ms · especialistas 35522/50165/60369/61181/46835ms.
Ojo: `llamadas` reportó 8 y las trazas son 6 — segunda confirmación de R-01.

## N-03 · contrastar() delega en la trazabilidad · 07:05
Estado: HECHA
Commit: (el anterior a este)
Autor: relevo (Claude) — SIN REVISIÓN INDEPENDIENTE
Qué cambió: `puntuar()` nuevo en trazabilidad.py; `contrastar()` lo usa y
devuelve precision, recall, f1, exactitud de tipo/severidad/ruteo y
accion_correcta, todo desde la atribución por evidencia. La sección 6 del CLI
las imprime. La comparación vieja por conjuntos de tipos se conserva pero queda
declarada como lo que es: legible, pero no la puntuación.
Verificación: compuerta verde, 172 tests (+6). Además smoke test del cableado
real de `contrastar()`, no solo del scorer aislado.
Nota: las tasas sin universo devuelven None, no 0.0. Un cero sobre cero casos
dice "falló todo" donde lo correcto es "no había nada que acertar".

## N-04 · puntuar.py — puntuación repetible · 07:35
Estado: HECHA
Commit: (el anterior a este)
Autor: relevo (Claude) — SIN REVISIÓN INDEPENDIENTE
Qué cambió: `scripts/ejecutablesBase/puntuar.py` nuevo. Provoca N escenarios,
corre uno por cada uno y agrega las métricas de N-03 en una tabla.
Verificación: compuerta verde, 178 tests (+6). Y probado de punta a punta contra
un stack en mock, sin tocar la nube.
Resultado del smoke: 3 escenarios, 9 incidentes, TOTAL 0% en todo. Es correcto —
el MockProvider devuelve evidencia genérica que no ancla contra ninguna línea
real, así que no detecta nada. El scorer lo reporta en vez de maquillarlo, y deja
a la vista por qué N-14 importa.
Notas de diseño: el TOTAL se recalcula sobre todos los incidentes en vez de
promediar las filas (promediar porcentajes de denominadores distintos miente),
y una corrida fallida no entra en el TOTAL. Ambas cosas con test.
Limitación documentada: el bus no tiene reset, así que la fila N ve también los
incidentes vivos de las filas anteriores. Cada fila se etiqueta con el escenario
que la disparó pero puntúa contra todo lo activo, que es lo que el agente vio.

## N-05 · Anclar la evidencia del triage · 08:05
Estado: HECHA
Commit: (el anterior a este)
Autor: relevo (Claude) — SIN REVISIÓN INDEPENDIENTE
Qué cambió: `validate_triage` acepta el volcado y sella cada cita igual que los
hallazgos; `app.js` pinta el sello también en las tarjetas de incidentes.
Verificación: compuerta verde, 182 tests (+4). Comprobado de punta a punta que
el evento SSE `triage` lleva `evidencia_verificada` y que app.js la consume.
Nota: marcar no es rechazar — un triage con evidencia parafraseada sigue siendo
utilizable, solo queda declarado cuál cita no ancla. Y sin volcado no se marca
nada, en vez de inventar un sello.
Refactor mínimo declarado: `_normalizar` y `_evidencia_anclada` se movieron
arriba de `validate_triage` para que estén definidas donde se usan. Contenido
sin tocar.

## N-06 · Patrón de identificadores · 08:25
Estado: HECHA
Commit: (el anterior a este)
Autor: relevo (Claude) — SIN REVISIÓN INDEPENDIENTE
Qué cambió: el patrón es case-insensitive y enumera los ocho prefijos que acuña
la clase `Ids` del generador (ALRT, TRX, SES, CRED, DEP, CTA, PED, HOST).
Antes cubría cuatro y `HOST-12` fallaba por mayúsculas.
Verificación: compuerta verde, 187 tests (+5), uno por formato.
Nota: se enumeran los prefijos en vez de aceptar cualquier `XXX-123`.
Sub-detectar es preferible: un identificador que se escapa pierde una
comprobación; un patrón demasiado amplio rechaza acciones legítimas y rompe la
corrida. Hay un test que fija que "Credential stuffing horizontal", "checkout" y
"24" NO cuentan — ese es el que protege contra ensancharlo de más.

## N-07 · Decidir el umbral de anclaje de acciones · 08:40
Estado: HECHA
Commit: c386016
Qué cambió: validate_finding ahora anula la acción si **alguna** cita no ancla,
salvo que todos los IDs de params aparezcan en las citas **sí** ancladas. Antes
solo anulaba si TODA la evidencia fallaba. Criterio documentado en docstring.
Verificación: compuerta verde, 199 tests (+2).
Nota: conservativo — prefiere bloquear una acción dudosa antes que dejar pasar
una acción con evidencia inventada. La excepción (cita irrelevante) evita
falsos negativos cuando el especialista cita de más pero los IDs que usa están
respaldados.

## N-08 · Reintento de especialistas · 08:55
Estado: HECHA
Commit: d6fad8c
Qué cambió: execute() pide el texto crudo y parsea aparte (igual que el triage).
Si el JSON no parsea o no valida, reintenta una vez devolviendo el error concreto.
Verificación: compuerta verde, 200 tests (+1).
Nota: mismo patrón que el triage — un especialista que devuelve JSON inválido la
primera vez y válido la segunda ahora produce un hallazgo completado, no fallido.

## N-09 · Dashboard unhealthy con barras en verde · 09:10
Estado: HECHA
Commit: 3f59c3e
Qué cambió: _derivar_health(metrics) deriva health de las métricas mostradas
(latency > 800, error_rate > 0.05, disk > 85) en vez de un flag pegajoso.
Verificación: compuerta verde, 205 tests (+5).
Nota: las alertas firing ya actualizan las métricas, y health se recalcula
después. Un servicio con métricas sanas pero alerta firing ya no se ve rojo.
