# Stack actual

| Pieza | Tecnología | Razón |
| --- | --- | --- |
| Runtime | Python 3.12, biblioteca estándar | Arranque desde clon limpio y superficie mínima |
| Servidor | `ThreadingHTTPServer` | Suficiente para el vertical slice; no se presenta como runtime productivo |
| Streaming | Server-Sent Events | Canal unidireccional simple para tokens y métricas |
| Inferencia | Kostra, formato compatible con OpenAI | Pasarela de tokens prepago con streaming y autenticación Bearer |
| Orquestación | Cuatro roles sobre `ChatProvider`, sin framework de agentes | El despacho y el presupuesto son código propio y auditable |
| Almacén | Supabase vía PostgREST y `urllib` | Persiste la cola de aprobación sin añadir dependencias de runtime |
| Frontend | HTML, CSS y JavaScript nativos | Sin build ni dependencias para la demo |
| Evaluación | JSON + script Python | Casos versionados y ejecución local o live |
| Empaquetado | Docker | Artefacto portable para elegir runtime cloud después |

El endpoint, los modelos, las cuotas y los precios **no forman parte estable del
stack**: son datos volátiles que se verifican antes de cada despliegue. Al
03-09-2026, Kostra expone `https://ai.kostra.cloud/v1/chat/completions` con estos
modelos y precios en CLP por millón de tokens (entrada / salida):

| Modelo | Contexto | Entrada | Salida |
| --- | --- | --- | --- |
| `deepseek-v4-flash` | 1.044.480 | 183 | 365 |
| `deepseek-v4-pro` | 1.044.480 | 2.186 | 4.373 |
| `glm-5.1` | 196.608 | 1.021 | 3.572 |
| `glm-5.2` | 196.608 | 1.325 | 4.164 |
| `claude-sonnet-4.6` | 200.000 | 4.732 | 21.630 |

El saldo es prepago y **compartido con la cuenta del chat web de Kostra**: no hay
saldo de API aparte. Kostra no ofrece recuperación de documentos, así que todo lo
que el modelo puede usar viaja en el prompt de cada request.

Detalle del proveedor y su taxonomía de errores: [ADR-0002](decisions/0002-proveedor-de-inferencia-kostra.md).
