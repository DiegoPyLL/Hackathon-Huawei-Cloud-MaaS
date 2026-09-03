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
| [0001](0001-vertical-slice-maas.md) | Vertical slice desacoplado de Huawei MaaS | Aceptada · superada en parte por 0002, 0003 y 0005 |
| [0002](0002-proveedor-de-inferencia-kostra.md) | Kostra como proveedor de inferencia | Aceptada |
| [0003](0003-orquestacion-multiagente.md) | Orquestación multiagente con cuatro roles | Aceptada |
| [0004](0004-acciones-acotadas-y-aprobacion-humana.md) | Catálogo cerrado de acciones y aprobación humana | Aceptada |
| [0005](0005-supabase-como-almacen.md) | Supabase como almacén, vía PostgREST | Aceptada |
| [0006](0006-ejecucion-programada-y-manual.md) | Ejecución programada en GitHub Actions y script manual | Aceptada |
| [0007](0007-traza-de-corrida-por-fase.md) | Traza de corrida por fase | Aceptada |
| [0008](0008-rango-de-refuerzo-con-ejecucion-real.md) | Rango de refuerzo con ejecución real (tool-calling) | Aceptada |

El 0001 sigue vigente en lo esencial —contrato `ChatProvider`, adaptadores separados, modo visible, sin fallback automático—. Lo que quedó atrás: el proveedor (0002), el límite de un solo agente (0003) y la ausencia de persistencia (0005). Cada ADR posterior nombra con precisión qué parte supera.
