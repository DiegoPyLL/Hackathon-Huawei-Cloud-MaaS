# 0002 — Kostra como proveedor de inferencia

> Estado: Aceptada · Fecha: 03-09-2026

Supera la afirmación del [0001](0001-vertical-slice-maas.md) de que la inferencia
ocurre en Huawei MaaS Standard API V2. El resto del 0001 —contrato `ChatProvider`,
adaptadores separados, modo visible, sin fallback automático— sigue vigente.

## Contexto

El 0001 se escribió cuando la cuenta y la región de Huawei todavía no se habían
validado, y describió el proveedor como "MaaS Standard API V2, CN-Hong Kong". Eso
dejó de ser cierto sin que ningún documento lo registrara: `config.py` apunta a
`https://ai.kostra.cloud/v1` con el modelo `deepseek-v4-pro`, mientras
`stack.md`, `alcance.md`, `vision.md` y `despliegue.md` seguían afirmando Huawei.

Un repositorio que miente sobre dónde corre su modelo no puede sostener el
invariante que más ha cuidado: que el modo de ejecución sea siempre visible y
honesto.

Kostra es una pasarela chilena de tokens prepago compatible con OpenAI. Datos
consultados en `https://ai.kostra.cloud/docs` el 03-09-2026:

- Base URL `https://ai.kostra.cloud/v1`, endpoint `POST /chat/completions`.
  También expone formato Anthropic en `POST /messages` (sin `/v1`) y `GET /models`.
- Autenticación `Authorization: Bearer sk-...`.
- Modelos y precio en CLP por millón de tokens (entrada / salida):

  | Modelo | Contexto | Entrada | Salida |
  | --- | --- | --- | --- |
  | `deepseek-v4-flash` | 1.044.480 | 183 | 365 |
  | `deepseek-v4-pro` | 1.044.480 | 2.186 | 4.373 |
  | `glm-5.1` | 196.608 | 1.021 | 3.572 |
  | `glm-5.2` | 196.608 | 1.325 | 4.164 |
  | `claude-sonnet-4.6` | 200.000 | 4.732 | 21.630 |

- Saldo prepago **compartido con la cuenta del chat web**, sin saldo de API aparte.
- Campos aceptados en el request: `model`, `messages`, `stream`, `temperature`,
  `max_tokens`, `top_p`, `stop`, `tools`, `fallbacks`.
- **No ofrece recuperación de documentos.** Es inferencia pura: todo lo que el
  modelo puede usar viaja en el prompt de cada request.

## Decisión

Se registró Kostra como el proveedor de inferencia del proyecto, con formato
compatible con OpenAI. La documentación se corrigió en consecuencia.

No se usa el campo `fallbacks`: declarar modelos de respaldo cambiaría en silencio
qué modelo respondió, y el proyecto muestra el modelo en cada respuesta. Si alguna
vez se activa, el evento `done` debe reportar el modelo que efectivamente contestó,
no el solicitado.

No se usa el campo `tools` nativo: las acciones del agente van por un catálogo
cerrado validado en servidor ([0004](0004-acciones-acotadas-y-aprobacion-humana.md)).

Se registró además la taxonomía de errores del proveedor, que hasta ahora se
colapsaba en un único mensaje genérico:

| Código | Significado | Efecto sobre la corrida |
| --- | --- | --- |
| `400` | Request malformado | Abortar: es un bug propio, no un fallo transitorio |
| `401` | Clave inválida | Abortar: es configuración |
| `402` | Saldo prepago agotado | Abortar y decirlo con todas sus letras; reintentar no sirve |
| `403` | Modelo no autorizado | Abortar esa tarea nombrando el modelo rechazado; no reintentar |
| `429` | Límite de tokens por minuto | Reintentar con espera; si persiste, la tarea queda fallida y la corrida sigue |
| `5xx` | Fallo del proveedor | Un reintento; después la tarea queda fallida y la corrida sigue |

La distinción entre abortar la corrida (`400`, `401`, `402`) y degradar una sola
tarea (`429`, `5xx`) es lo que evita que un problema de cuenta se disfrace de fallo
técnico aleatorio.

## Alternativas descartadas

| Alternativa | Por qué se descartó |
| --- | --- |
| Migrar a Huawei MaaS para que los documentos vuelvan a ser ciertos | Cambiar el sistema para no tener que corregir un documento es invertir el orden; la documentación describe el estado actual, no lo justifica |
| Editar el 0001 para que dijera Kostra | Los ADR no se editan (regla 2 de `decisions/README.md`); borraría la evidencia de que la decisión cambió |
| Dejar la contradicción y aclararla solo en la demo | El repositorio es parte de la entrega; un jurado que lee `stack.md` recibe información falsa |
| Soportar Kostra y Huawei a la vez tras `ChatProvider` | Duplica documentación y pruebas de un proveedor que hoy no se usa; el contrato ya permite añadirlo cuando exista la necesidad |
| Usar `fallbacks` para sobrevivir a un modelo caído | Rompe la trazabilidad de qué modelo respondió, que es el invariante central del proyecto |

## Consecuencias

**A favor:** la documentación vuelve a ser verdad. El precio por modelo queda
explícito, lo que hace posible razonar sobre costo antes de implementar. La
taxonomía de errores permite que una corrida multiagente distinga un problema de
cuenta de un fallo técnico.

**En contra:** el nombre `MaaSProvider` y el prefijo `MAAS_*` de las variables de
entorno nombran un proveedor que no es el que se usa. Renombrarlos toca `.env`,
`Dockerfile`, `config.py`, `dotenv.py` y las pruebas; se acepta la deuda por ahora
y queda registrada aquí. Además, el saldo prepago compartido con el chat web es un
punto de fallo operativo: alguien usando el chat puede dejar la demo sin saldo.

**Coste de revertir:** bajo. El contrato `ChatProvider` del 0001 sigue siendo la
frontera; cambiar de proveedor es escribir otro adaptador.

## Fuentes volátiles

- [Kostra — documentación de API](https://ai.kostra.cloud/docs) (consultada 03-09-2026)
- Precios, modelos y límites cambian sin aviso: reverificar antes de cada despliegue y antes de la demo.
