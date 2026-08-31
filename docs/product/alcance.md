# Alcance del vertical slice

## Incluido

- Interfaz web responsive y accesible.
- Conversación de una o varias intervenciones con límite de entrada.
- Streaming SSE desde backend al navegador.
- Huawei MaaS Standard API V2 mediante HTTPS y API key.
- Modo `mock` determinista, elegido explícitamente.
- Modelo, modo y latencia visibles.
- Pruebas de contrato, integración HTTP, evaluación y smoke test.
- Imagen de contenedor sin dependencias de runtime adicionales.

## Fuera de alcance por ahora

- Autenticación de usuarios finales y persistencia de conversaciones.
- RAG, base vectorial, herramientas o flujo agente.
- Moderación específica del dominio de negocio.
- Aprovisionamiento automático de infraestructura Huawei.
- Alta disponibilidad, autoscaling y observabilidad administrada.
- Afirmar calidad del modelo live antes de ejecutar la evaluación con la cuenta y
  región reales.

Agregar alguno de estos elementos requiere demostrar primero qué fallo o métrica
del vertical actual lo justifica.
