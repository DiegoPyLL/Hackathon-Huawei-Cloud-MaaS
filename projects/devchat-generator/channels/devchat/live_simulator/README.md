# Dev Chat — simulador en vivo

Chat tipo Slack que se genera solo: varios hilos (charla normal e incidentes)
corren en paralelo y se van intercalando mensaje a mensaje, igual que en un
canal real con varias conversaciones abiertas a la vez. Sirve un frontend en
el navegador.

Reusa el vocabulario y la taxonomía de `channels/devchat/generator/`
(mismos 8 tipos de incidente) — esto no reemplaza al generador batch, es un
modo "en vivo" para demo.

## Autenticación

Ningún sistema de mensajería real deja sus endpoints abiertos — cuando esto
se reemplace por Slack/Teams de verdad, el agente va a necesitar un token de
bot para conectarse. Para simular esa misma restricción, `/api/history`,
`/api/channels`, `/api/speed` y `/ws` exigen un token:

- REST: header `Authorization: Bearer <token>`
- WebSocket: query param `?token=<token>` (los navegadores no pueden mandar
  headers custom en el handshake de WS, por eso va en la URL)

El token sale de la variable de entorno `DEVCHAT_API_TOKEN`; si no se
setea, usa el default de desarrollo `devchat-dev-token` (se imprime en la
consola al arrancar el server). El HTML que sirve `/` inyecta el token real
del server, así que el frontend siempre queda sincronizado sin tocar nada
a mano.

`/api/stats` queda deliberadamente sin proteger — es el endpoint de
monitoreo/groundtruth para nosotros, no algo que un chat real expondría ni
que el agente vaya a tocar.

## Dos salidas, separadas a propósito

Todo mensaje que se genera tiene una versión "pública" y una "groundtruth".
Nunca se mezclan — el objetivo es que ni el frontend ni el agente que se
construya después puedan hacer trampa leyendo la respuesta.

- **`channels/devchat/data/devchat_live_public.jsonl`** — lo único que viaja
  por WebSocket, lo único que alimenta `/api/history`, y por lo tanto lo
  único que ve el chat en el navegador (y lo que va a leer el agente de
  triage más adelante): `seq, canal, autor, rol, timestamp, texto`. Sin
  `thread_id`, sin `categoria_real`, sin `es_incidente`, sin severidad —
  visualmente (y para el agente) un mensaje de incidente es indistinguible
  de charla normal, tiene que clasificarlo solo.
- **`channels/devchat/data/devchat_live_groundtruth.jsonl`** — la verdad
  completa por mensaje (`categoria_real`, `es_incidente`, `severidad_real`,
  `thread_id`, etc.), con el mismo `seq` para poder cruzarlo contra el feed
  público después. Nunca se transmite al frontend. Es el archivo que vas a
  usar para medir precisión/recall del agente una vez que exista.

Ambos archivos se reinician cada vez que arranca el servidor.

## Monitoreo en vivo — `/api/stats`

Endpoint aparte, no linkeado desde la UI del chat, con los contadores reales
acumulados desde que arrancó el servidor:

```json
{
  "total_mensajes": 34,
  "total_mensajes_incidente": 4,
  "total_mensajes_normales": 30,
  "total_hilos": 11,
  "hilos_incidente": 2,
  "hilos_normales": 9,
  "hilos_por_categoria": {"ruido": 4, "solicitud": 5, "datos": 2},
  "hilos_por_severidad": {"alta": 1, "media": 1}
}
```

`hilos_*` cuenta incidentes/conversaciones reales (eventos), `mensajes_*`
cuenta mensajes individuales — son dos unidades distintas a propósito, un
incidente típico genera varios mensajes.

## Arrancar

Desde `incident-triage-agent/` (ya existe un venv en `.venv`):

```powershell
.\.venv\Scripts\python.exe -m uvicorn channels.devchat.live_simulator.server:app --app-dir channels\devchat\live_simulator --reload --port 8000
```

o más simple, parado en esta carpeta:

```powershell
cd channels\devchat\live_simulator
..\..\..\.venv\Scripts\python.exe -m uvicorn server:app --reload --port 8000
```

Abrir http://localhost:8000

## Controles
- Sidebar: filtrar por canal o ver "Todos los canales".
- Selector de velocidad (lento/normal/rápido): ajusta el ritmo de emisión en
  vivo, sin reiniciar el servidor — útil para controlar el pacing en la demo.

## Notas de diseño
- Hasta 5 hilos activos en paralelo (`MAX_ACTIVE_THREADS` en `server.py`).
  Esto genera de forma natural el caso de "hilos multi-incidente mezclados en
  el mismo canal" que quedó pendiente en `NOTES.md` — no hay que simularlo
  aparte, sale solo de correr el simulador un rato.
- El frontend no recibe el groundtruth (`es_incidente`, `categoria_real`,
  etc.) ni siquiera en el JSON que llega por WebSocket — no es solo que no
  se muestre, el dato no viaja. Todo mensaje se ve exactamente igual. El
  groundtruth completo vive aparte, en `devchat_live_groundtruth.jsonl`.
- Timestamps son la hora real del servidor (streaming en vivo), a diferencia
  del generador batch que usa fechas históricas sintéticas.
