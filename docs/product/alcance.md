# Alcance del vertical slice

## Incluido

- Interfaz web responsive y accesible.
- Conversación de una o varias intervenciones con límite de entrada.
- Streaming SSE desde backend al navegador.
- Inferencia en Kostra, formato compatible con OpenAI, mediante HTTPS y API key.
- Modo `mock` determinista, elegido explícitamente.
- Modelo, modo y latencia visibles.
- **Flujo agente**: cuatro roles (Orquestador, DBA, SysAdmin, SecOps) con despacho
  fan-out / fan-in y presupuesto acotado de llamadas.
- **Catálogo cerrado de acciones correctivas** y cola de aprobación humana: ninguna
  acción se ejecuta sin que una persona la apruebe.
- **Persistencia en Supabase** de corridas, hallazgos y aprobaciones.
- Pruebas de contrato, integración HTTP, evaluación y smoke test.
- Imagen de contenedor sin dependencias de runtime adicionales.

## Fuera de alcance por ahora

- **RAG y base vectorial.** No por postergación: Kostra no ofrece recuperación de
  documentos. Todo lo que el modelo puede usar viaja en el prompt de cada request.
- Autenticación de usuarios finales. La demo asume un único operador en
  `127.0.0.1`; el riesgo aceptado está registrado en
  [`../architecture/modelo-de-datos.md`](../architecture/modelo-de-datos.md).
- Ejecución automática de acciones sin aprobación humana, incluidas las de riesgo
  bajo del catálogo.
- Acciones fuera del catálogo cerrado, y en particular SQL generado por el modelo.
- Moderación específica del dominio de negocio.
- Aprovisionamiento automático de infraestructura Huawei.
- Alta disponibilidad, autoscaling y observabilidad administrada.
- Afirmar calidad del modelo live antes de ejecutar la evaluación con la cuenta
  real.

Agregar alguno de estos elementos requiere demostrar primero qué fallo o métrica
del vertical actual lo justifica. Las tres primeras incorporaciones de la lista de
arriba siguieron esa regla: sus ADR
([0003](../architecture/decisions/0003-orquestacion-multiagente.md),
[0004](../architecture/decisions/0004-acciones-acotadas-y-aprobacion-humana.md),
[0005](../architecture/decisions/0005-supabase-como-almacen.md)) nombran la brecha
concreta que las motivó.
