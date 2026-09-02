# 0002 — FastAPI y pipeline acotado para el Guardian

> Estado: Aceptada · Fecha: 02-09-2026 · Reemplaza a [0001](0001-vertical-slice-maas.md)

## Contexto

El [ADR 0001](0001-vertical-slice-maas.md) fijó un vertical slice sin dependencias
de runtime sobre `ThreadingHTTPServer`. Ese contrato sigue siendo correcto para un
único endpoint de chat, pero el AI Cloud Deployment Guardian añade análisis de
Pull Requests, validación de entrada por esquema y dos endpoints más.

Además, la promesa de optimización de tokens del caso no se cumplía: el fetcher
descargaba el diff como un único string, de modo que el índice de importancia no
podía recortar nada. Medido sobre el PR #3, se enviaban al modelo 6.072 tokens
donde bastan 2.514.

Tampoco estaba garantizado que el modelo configurado soporte el campo `tools` de
la API de inferencia, requisito del comportamiento agentic del caso.

## Decisión

1. **FastAPI + uvicorn** como capa HTTP, con Pydantic validando el contrato
   público. `ThreadingHTTPServer` se elimina.
2. **El patch viaja por archivo**, no como diff monolítico, y el índice de
   importancia decide qué archivos llegan al modelo. Una llamada menos a la API
   de GitHub, porque `/pulls/{n}/files` ya devuelve el patch.
3. **Protocolo JSON propio** en lugar de tool calling nativo: el modelo responde
   `{"action": "need_files", ...}` o `{"action": "findings", ...}` y el backend
   resuelve el bucle. No depende de capacidades del proveedor y se ejercita con
   `MockProvider`.
4. **Las reglas críticas viven fuera del modelo.** Un hallazgo `CRITICAL` del
   Rule Engine bloquea el despliegue por sí solo; el modelo solo añade hallazgos.
5. **Presupuesto explícito**: máximo 5 lecturas de archivo, 12.000 tokens de
   contexto, 8 KB por archivo y prohibición de releer un archivo ya servido.

`config.py`, `provider.py` y `service.py` no cambian: ya eran agnósticos del
transporte, que era el objetivo del ADR 0001.

## Alternativas descartadas

| Alternativa | Por qué se descartó |
| --- | --- |
| Mantener `ThreadingHTTPServer` | Obligaba a validar a mano tres endpoints y sus esquemas |
| Tool calling nativo de la API | Asume soporte del modelo; el fallo aparecería durante la demo |
| Un turno de LLM por cada paso del caso | El prompt se repite en cada turno y el coste crece de forma cuadrática |
| Calcular coste y riesgo con el LLM | Es aritmética: gastaría tokens en algo determinista y auditable |
| Enviar el diff completo y confiar en el modelo | Es exactamente el problema que este ADR corrige |

## Consecuencias

**A favor:** el envío al modelo se reduce a la mitad de forma medida, el análisis
cuesta una llamada (dos si el usuario pide parche), la decisión es auditable y el
bucle agentic es testeable sin red.

**En contra:** aparecen tres dependencias de runtime donde antes no había ninguna,
y el umbral de importancia (50) es un parámetro que habrá que calibrar con más
Pull Requests reales.

**Coste de revertir:** medio. La capa HTTP es sustituible, pero el paquete
`guardian` asume que cada archivo trae su propio patch.

## Fuentes volátiles

- [GitHub: List pull requests files](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests-files)
- [MaaS Standard API V2](https://support.huaweicloud.com/intl/en-us/model-call-maas/model-call-019.html)
