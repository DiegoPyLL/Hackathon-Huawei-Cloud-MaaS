# Arquitectura

Cómo está construido el proyecto y por qué. Describe el estado actual, no el ideal.

| Documento | Contenido |
| --- | --- |
| [`decisions/`](decisions/) | ADRs: decisiones técnicas con su contexto y consecuencias |
| [`stack.md`](stack.md) | Tecnologías en uso y qué resuelve cada una |
| [`flujo-agentes.md`](flujo-agentes.md) | Los cuatro roles, las seis fases, la tabla de ruteo y el presupuesto de una corrida |
| [`contratos-agentes.md`](contratos-agentes.md) | Los contratos JSON entre roles, su validación y el catálogo cerrado de acciones |
| [`modelo-de-datos.md`](modelo-de-datos.md) | Entidades, relaciones y reglas de integridad del almacén Supabase |
| _(pendiente)_ `estructura.md` | Organización de carpetas del código y qué vive en cada una |

**Aquí no van:** las razones de una decisión pasada (eso es un ADR, no una edición de estos documentos) ni instrucciones de despliegue (`operations/`).
