# Visión de MaaS Decision Brief

## Problema

Los prototipos GenAI suelen mostrar una respuesta llamativa, pero no dejan claro
si la integración real funciona, cuánto tarda ni cómo se repetirá la prueba. En
una hackathon, esa ambigüedad reduce confianza y consume tiempo de explicación.

## Usuario

Un equipo necesita convertir un reto en una recomendación accionable y demostrar
al jurado, en pocos minutos, qué modelo respondió, en qué modo y con qué latencia.

## Propuesta de valor

MaaS Decision Brief transforma una descripción abierta en un brief priorizado y
acompaña cada resultado con evidencia operativa visible.

## Promesa

> De un reto ambiguo a una decisión demostrable en una sola interacción.

## Señales de éxito de la fase actual

- Un clon limpio puede iniciar la demo local sin credenciales.
- El mismo contrato funciona con simulación determinista y Huawei MaaS.
- La interfaz nunca confunde ambos modos.
- Un dataset versionado detecta regresiones básicas.
- Un smoke test puede exigir y probar explícitamente el modo `live`.

La vertical actual valida el mecanismo. Antes de cerrar la propuesta para el
jurado se debe reemplazar el reto genérico por un problema de negocio concreto y
actualizar prompt, dataset y copy sin cambiar el límite del proveedor.
