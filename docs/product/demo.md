# Guion de demo

## Preparación

1. Ejecutar pruebas y evaluación.
2. Iniciar el servidor en `live` y comprobar `/api/health`.
3. Ejecutar `scripts/prueba-humo.py --require-mode live`.
4. Mantener una segunda terminal lista para iniciar `mock`, claramente etiquetado,
   solo si la red o el proveedor no están disponibles.

## Guion de tres minutos

**0:00–0:30 — problema.** Los prototipos de IA son difíciles de juzgar cuando no
se distingue una integración real de una respuesta preparada.

**0:30–1:30 — interacción.** Introducir un reto del dominio elegido. Señalar el
streaming y no explicar todavía la arquitectura.

**1:30–2:10 — evidencia.** Mostrar badge `LIVE`, modelo y latencia. Ejecutar o
enseñar el smoke test que exige `live`.

**2:10–2:40 — ingeniería.** Explicar en una frase el adaptador reemplazable y el
dataset de evaluación. Mostrar el resultado de los casos solo si es evidencia
reciente.

**2:40–3:00 — impacto.** Cerrar con la métrica de negocio del caso de uso final,
no con una lista de servicios cloud.

## Regla de contingencia

Si falla MaaS, mostrar el error y cambiar manualmente a `mock`. Decir de forma
explícita que se está demostrando UX y contrato local, no conectividad cloud.
