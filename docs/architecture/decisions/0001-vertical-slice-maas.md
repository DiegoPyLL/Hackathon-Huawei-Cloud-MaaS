# 0001 — Vertical slice desacoplado de Huawei MaaS

## Contexto

El repositorio era una plantilla web sin aplicación. La hackathon exige demostrar
valor GenAI rápidamente y distinguir evidencia cloud real de una simulación. La
cuenta, región y API key todavía no se han validado desde este entorno.

La documentación vigente de Huawei indica que MaaS Standard API V2 ofrece chat
streaming mediante `POST /v2/chat/completions`, autenticación Bearer y, al
31-08-2026, disponibilidad en CN-Hong Kong.

## Decisión

Se implementó un vertical slice Python sin dependencias de runtime, con un
contrato interno `ChatProvider`, adaptadores separados `MaaSProvider` y
`MockProvider`, streaming SSE y modo visible en cada respuesta.

No existe fallback automático de `live` a `mock`.

## Alternativas descartadas

| Alternativa | Por qué se descartó |
| --- | --- |
| Integrar el payload Huawei directamente en la interfaz | Expondría la API key y acoplaría producto y proveedor |
| Adoptar un framework y SDK antes del primer flujo | Añadía instalación y superficie sin mejorar la demostración inicial |
| Ocultar fallos live con una respuesta simulada | Convertiría una demo aparentemente exitosa en evidencia falsa |
| Añadir RAG o agentes desde el inicio | No existe todavía una brecha evaluada que justifique esa complejidad |

## Consecuencias

**A favor:** arranque inmediato, prueba determinista, límite de proveedor claro y
evidencia visible.

**En contra:** el servidor estándar no es la elección final de producción y el
dataset actual solo valida el contrato mínimo, no calidad de un dominio concreto.

**Coste de revertir:** bajo. El frontend y el servicio dependen del contrato
interno; se puede sustituir servidor o proveedor sin cambiar el caso de uso.

## Fuentes volátiles

- [MaaS Standard API V2](https://support.huaweicloud.com/intl/en-us/model-call-maas/model-call-019.html)
- [Lista de modelos MaaS](https://support.huaweicloud.com/intl/en-us/model-call-maas/usermanual_maas_0008.html)
