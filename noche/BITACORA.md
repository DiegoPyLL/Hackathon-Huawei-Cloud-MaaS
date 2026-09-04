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
