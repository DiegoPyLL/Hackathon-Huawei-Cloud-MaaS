# Decisiones de arquitectura (ADR)

Un ADR registra **una** decisión técnica con consecuencias: por qué se tomó, qué se descartó y qué cuesta revertirla.

## Reglas

1. Un archivo por decisión: `NNNN-titulo-en-kebab-case.md`, numeración correlativa desde `0001`.
2. **Los ADR no se editan.** Una decisión que cambia se registra en un ADR nuevo que marca al anterior como `Reemplazado por NNNN`.
3. Se escribe en pasado y en concreto: qué se decidió, no qué se está evaluando.
4. Si una decisión no tiene alternativas descartadas, probablemente no era una decisión y no necesita ADR.

## Cuándo escribir uno

Elección de framework, base de datos o proveedor · estrategia de renderizado (SSG/SSR/ISR) · modelo de autenticación · introducción de una dependencia difícil de quitar · cualquier cosa que en seis meses alguien preguntará "¿por qué está hecho así?".

## Índice

| # | Decisión | Estado |
| --- | --- | --- |
| [0000](0000-plantilla.md) | Plantilla | Plantilla |
