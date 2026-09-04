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
