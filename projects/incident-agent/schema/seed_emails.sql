-- ============================================================
-- Seed: bandeja de soporte derivada de los hilos de dev chat
--
-- ARCHIVO GENERADO. No editar a mano.
--   python projects/incident-agent/generator/generar_seed_correos.py
--
-- Cada correo viene de un hilo de dev_chat_tickets.jsonl: el cuerpo es la
-- transcripcion del hilo y el groundtruth del hilo define el ticket. Los correos
-- de categoria "ruido" y "solicitud", y los seguimientos, no generan incidente:
-- quedan procesados sin ticket, que es el registro de que se descartaron.
--
-- Uso:
--   supabase db execute -f projects/incident-agent/schema/seed_emails.sql
--   (o pegar el archivo completo en el SQL editor del proyecto)
--
-- Es idempotente: los UUID se derivan del message_id con md5.
--   email     -> md5(message_id)::uuid
--   incidente -> md5('inc:' || message_id)::uuid
--   saliente  -> md5('out:' || message_id)::uuid
-- ============================================================

-- ------------------------------------------------------------
-- 1) Correos entrantes crudos (50)
-- ------------------------------------------------------------
insert into emails_entrantes (id, message_id, remitente, asunto, cuerpo, headers, recibido_en)
select
  md5(v.mid)::uuid,
  v.mid,
  v.remitente,
  v.asunto,
  v.cuerpo,
  jsonb_build_object(
    'To', 'soporte.jsonch@gmail.com',
    'From', v.remitente,
    'X-Devchat-Thread', v.thread_id,
    'X-Devchat-Canal', v.canal,
    'X-Seed', 'devchat'
  ),
  v.recibido_en::timestamptz
from (values
('<DEVCHAT-0035@devchat.local>', 'nano_sre@nortech.example', 'jajaja alguien vio el video que mandé', '[08:38] nano_sre (sre): jajaja alguien vio el video que mandé
[08:38] fely.ops (sre): dale, buen finde!
[08:46] nano_sre (sre): ah ok gracias por avisar', 'DEVCHAT-0035', '#on-call', '2026-06-10T08:38:00'),
('<DEVCHAT-0030@devchat.local>', 'valen_pm@nortech.example', 'encontré un bug en reportes, el descuento no se aplica bien', '[13:05] valen_pm (pm): encontré un bug en reportes, el descuento no se aplica bien
[13:12] seba_infra (sre): reproduje en staging, es el mismo comportamiento
[13:42] valen_pm (pm): era un edge case con montos negativos, el fix ya está en review', 'DEVCHAT-0030', '#alerts-prod', '2026-06-15T13:05:00'),
('<DEVCHAT-0021@devchat.local>', 'diego.lead@nortech.example', 'nano_sre reportó que el flujo de reportes se corta a mitad de camino', '[11:02] diego.lead (lead): nano_sre reportó que el flujo de reportes se corta a mitad de camino
[11:11] diego.lead (lead): esto viene del último deploy o es viejo?
[11:26] nano_sre (sre): reproduje en staging, es el mismo comportamiento
[11:27] diego.lead (lead): puedes mandar un ejemplo con el id del caso?
[11:34] diego.lead (lead): esto me suena a INC-2026-0011, saturación de disco en reportes
[11:52] diego.lead (lead): era un edge case con montos negativos, el fix ya está en review', 'DEVCHAT-0021', '#incidentes', '2026-06-16T11:02:00'),
('<DEVCHAT-0021-seg@devchat.local>', 'diego.lead@nortech.example', 'Re: nano_sre reportó que el flujo de reportes se corta a mitad de camino', '[11:52] diego.lead (lead): era un edge case con montos negativos, el fix ya está en review', 'DEVCHAT-0021', '#incidentes', '2026-06-16T11:52:02'),
('<DEVCHAT-0005@devchat.local>', 'nano_sre@nortech.example', 'checkout está caído, nadie puede hacer login', '[07:04] nano_sre (sre): 🚨 checkout está caído, nadie puede hacer login
[07:14] camila.rios (dev): lo mismo en staging o solo prod?
[07:23] nano_sre (sre): pod de checkout en crashloop, viendo logs
[07:25] seba_infra (sre): clientes ya están reclamando por redes sociales
[07:34] seba_infra (sre): confirmado, healthcheck en rojo desde las 07:04
[07:39] camila.rios (dev): era un deploy mal aplicado, se hizo rollback y ya volvió', 'DEVCHAT-0005', '#on-call', '2026-06-17T07:04:00'),
('<DEVCHAT-0005-seg@devchat.local>', 'camila.rios@nortech.example', 'Re: checkout está caído, nadie puede hacer login', '[07:39] camila.rios (dev): era un deploy mal aplicado, se hizo rollback y ya volvió', 'DEVCHAT-0005', '#on-call', '2026-06-17T07:39:45'),
('<DEVCHAT-0011@devchat.local>', 'diego.lead@nortech.example', 'login-web está lentísimo, p95 se fue a las nubes', '[07:49] diego.lead (lead): login-web está lentísimo, p95 se fue a las nubes
[07:57] diego.lead (lead): cpu del login-web al 90%, parece cuello de botella
[08:17] nano_sre (sre): se escaló el número de réplicas y bajó la latencia', 'DEVCHAT-0011', '#incidentes', '2026-06-18T07:49:00'),
('<DEVCHAT-0001@devchat.local>', 'camila.rios@nortech.example', 'bd-clientes volvió a la normalidad, era una alerta vieja, falsa alarma', '[17:21] camila.rios (dev): bd-clientes volvió a la normalidad, era una alerta vieja, falsa alarma
[17:22] camila.rios (dev): ah ok gracias por avisar
[17:27] valen_pm (pm): dale, buen finde!', 'DEVCHAT-0001', '#incidentes', '2026-06-22T17:21:00'),
('<DEVCHAT-0027@devchat.local>', 'pao_qa@nortech.example', 'faltan registros en pagos, el batch de anoche no corrió completo', '[13:46] pao_qa (qa): faltan registros en pagos, el batch de anoche no corrió completo
[13:53] bpereira (dev): esto puede haber llegado a reportes ya generados
[14:05] bpereira (dev): se re-ejecutó el batch y se reconciliaron los datos', 'DEVCHAT-0027', '#alerts-prod', '2026-06-25T13:46:00'),
('<DEVCHAT-0022@devchat.local>', 'valen_pm@nortech.example', 'tengo tickets de gente bloqueada después del reset de clave', '[09:47] valen_pm (pm): tengo tickets de gente bloqueada después del reset de clave
[10:01] camila.rios (dev): parece que el token expira antes de tiempo
[10:06] seba_infra (sre): es general o algún segmento en particular?
[10:14] root_marce (sre): esto me suena a INC-2026-0011, saturación de disco en reportes', 'DEVCHAT-0022', '#incidentes', '2026-06-28T09:47:00'),
('<DEVCHAT-0006@devchat.local>', 'nano_sre@nortech.example', 'jajaja alguien vio el video que mandé', '[16:41] nano_sre (sre): jajaja alguien vio el video que mandé
[16:47] nano_sre (sre): ah ok gracias por avisar
[16:57] bpereira (dev): dale, buen finde!', 'DEVCHAT-0006', '#dev-backend', '2026-06-28T16:41:00'),
('<DEVCHAT-0031@devchat.local>', 'camila.rios@nortech.example', 'jajaja alguien vio el video que mandé', '[21:28] camila.rios (dev): jajaja alguien vio el video que mandé
[21:31] camila.rios (dev): dale, buen finde!', 'DEVCHAT-0031', '#incidentes', '2026-06-28T21:28:00'),
('<DEVCHAT-0014@devchat.local>', 'fely.ops@nortech.example', 'api-gateway está lentísimo, p95 se fue a las nubes', '[12:42] fely.ops (sre): api-gateway está lentísimo, p95 se fue a las nubes
[12:49] pao_qa (qa): cuántos usuarios afectados aprox?
[13:04] camila.rios (dev): se escaló el número de réplicas y bajó la latencia', 'DEVCHAT-0014', '#alerts-prod', '2026-07-03T12:42:00'),
('<DEVCHAT-0024@devchat.local>', 'jcontreras@nortech.example', 'nos estamos quedando sin conexiones en el pool de login-web', '[07:18] jcontreras (dev): nos estamos quedando sin conexiones en el pool de login-web
[07:23] camila.rios (dev): hay algo generando logs de más de lo normal?
[07:24] jcontreras (dev): esto me suena a INC-2025-0013, registros faltantes en login-web tras el batch nocturno
[07:44] camila.rios (dev): se aumentó el pool de conexiones', 'DEVCHAT-0024', '#incidentes', '2026-07-05T07:18:00'),
('<DEVCHAT-0018@devchat.local>', 'valen_pm@nortech.example', 'cola-mensajes no responde desde hace como 10 min', '[10:42] valen_pm (pm): cola-mensajes no responde desde hace como 10 min
[10:54] fely.ops (sre): clientes ya están reclamando por redes sociales
[10:58] diego.lead (lead): pod de cola-mensajes en crashloop, viendo logs
[11:02] fely.ops (sre): lo mismo en staging o solo prod?
[11:09] diego.lead (lead): confirmado, healthcheck en rojo desde las 10:42', 'DEVCHAT-0018', '#alerts-prod', '2026-07-08T10:42:00'),
('<DEVCHAT-0018-seg@devchat.local>', 'diego.lead@nortech.example', 'Re: cola-mensajes no responde desde hace como 10 min', '[11:09] diego.lead (lead): confirmado, healthcheck en rojo desde las 10:42', 'DEVCHAT-0018', '#alerts-prod', '2026-07-08T11:09:56'),
('<DEVCHAT-0012@devchat.local>', 'valen_pm@nortech.example', 'rate limit de login-web saltando constantemente', '[17:39] valen_pm (pm): rate limit de login-web saltando constantemente
[17:47] camila.rios (dev): hay algo generando logs de más de lo normal?', 'DEVCHAT-0012', '#dev-backend', '2026-07-09T17:39:00'),
('<DEVCHAT-0004@devchat.local>', 'bpereira@nortech.example', 'buen finde a todos!', '[19:06] bpereira (dev): buen finde a todos!
[19:07] diego.lead (lead): dale, buen finde!
[19:15] diego.lead (lead): ah ok gracias por avisar', 'DEVCHAT-0004', '#general-dev', '2026-07-14T19:06:00'),
('<DEVCHAT-0026@devchat.local>', 'jcontreras@nortech.example', 'rate limit de cola-mensajes saltando constantemente', '[19:55] jcontreras (dev): rate limit de cola-mensajes saltando constantemente
[20:02] root_marce (sre): hay algo generando logs de más de lo normal?
[20:06] camila.rios (dev): se aumentó el pool de conexiones', 'DEVCHAT-0026', '#alerts-prod', '2026-07-15T19:55:00'),
('<DEVCHAT-0013@devchat.local>', 'nano_sre@nortech.example', 'alguien sabe cómo se configura el ambiente de pagos en local?', '[21:20] nano_sre (sre): alguien sabe cómo se configura el ambiente de pagos en local?
[21:24] camila.rios (dev): yo tengo la doc, te la paso
[21:29] nano_sre (sre): listo, te agrego al repo
[21:43] nano_sre (sre): dale, cuadremos para mañana', 'DEVCHAT-0013', '#dev-backend', '2026-07-15T21:20:00'),
('<DEVCHAT-0002@devchat.local>', 'seba_infra@nortech.example', 'oye cola-mensajes tira 502 en todos los requests, alguien más?', '[18:01] seba_infra (sre): oye cola-mensajes tira 502 en todos los requests, alguien más?
[18:09] seba_infra (sre): lo mismo en staging o solo prod?
[18:14] diego.lead (lead): pod de cola-mensajes en crashloop, viendo logs
[18:16] jcontreras (dev): confirmado, healthcheck en rojo desde las 18:01
[18:25] seba_infra (sre): esto me suena a INC-2026-0007, cálculo incorrecto en notificaciones para montos negativos
[18:41] jcontreras (dev): era un deploy mal aplicado, se hizo rollback y ya volvió', 'DEVCHAT-0002', '#dev-backend', '2026-07-16T18:01:00'),
('<DEVCHAT-0002-seg@devchat.local>', 'jcontreras@nortech.example', 'Re: oye cola-mensajes tira 502 en todos los requests, alguien más?', '[18:41] jcontreras (dev): era un deploy mal aplicado, se hizo rollback y ya volvió', 'DEVCHAT-0002', '#dev-backend', '2026-07-16T18:41:30'),
('<DEVCHAT-0008@devchat.local>', 'seba_infra@nortech.example', 'bpereira reportó que el flujo de batch-facturacion se corta a mitad de camino', '[09:53] seba_infra (sre): bpereira reportó que el flujo de batch-facturacion se corta a mitad de camino
[10:06] bpereira (dev): reproduje en staging, es el mismo comportamiento
[10:35] diego.lead (lead): era un edge case con montos negativos, el fix ya está en review', 'DEVCHAT-0008', '#alerts-prod', '2026-07-21T09:53:00'),
('<DEVCHAT-0036@devchat.local>', 'camila.rios@nortech.example', 'seba_infra reportó que el flujo de cola-mensajes se corta a mitad de camino', '[13:11] camila.rios (dev): seba_infra reportó que el flujo de cola-mensajes se corta a mitad de camino
[13:16] nano_sre (sre): esto viene del último deploy o es viejo?
[13:29] seba_infra (sre): reproduje en staging, es el mismo comportamiento
[13:44] seba_infra (sre): puedes mandar un ejemplo con el id del caso?
[13:50] camila.rios (dev): era un edge case con montos negativos, el fix ya está en review', 'DEVCHAT-0036', '#incidentes', '2026-07-23T13:11:00'),
('<DEVCHAT-0036-seg@devchat.local>', 'camila.rios@nortech.example', 'Re: seba_infra reportó que el flujo de cola-mensajes se corta a mitad de camino', '[13:50] camila.rios (dev): era un edge case con montos negativos, el fix ya está en review', 'DEVCHAT-0036', '#incidentes', '2026-07-23T13:50:13'),
('<DEVCHAT-0023@devchat.local>', 'camila.rios@nortech.example', 'webhook de cache-redis dejó de llegar', '[15:41] camila.rios (dev): webhook de cache-redis dejó de llegar
[15:49] camila.rios (dev): puede ser rate limit de nuestro lado
[15:58] nano_sre (sre): revisé el status page del proveedor, dice operativo, raro
[16:10] camila.rios (dev): abrí ticket con el proveedor, esperando respuesta', 'DEVCHAT-0023', '#alerts-prod', '2026-07-23T15:41:00'),
('<DEVCHAT-0039@devchat.local>', 'nano_sre@nortech.example', 'usuarios reportando que tarda una eternidad en cargar', '[21:23] nano_sre (sre): usuarios reportando que tarda una eternidad en cargar
[21:26] fely.ops (sre): cuántos usuarios afectados aprox?
[21:31] root_marce (sre): se escaló el número de réplicas y bajó la latencia', 'DEVCHAT-0039', '#alerts-prod', '2026-07-25T21:23:00'),
('<DEVCHAT-0017@devchat.local>', 'nano_sre@nortech.example', 'jajaja alguien vio el video que mandé', '[16:33] nano_sre (sre): jajaja alguien vio el video que mandé
[16:38] fely.ops (sre): ah ok gracias por avisar
[16:52] nano_sre (sre): dale, buen finde!', 'DEVCHAT-0017', '#incidentes', '2026-07-26T16:33:00'),
('<DEVCHAT-0028@devchat.local>', 'jcontreras@nortech.example', 'pao_qa reportó que el flujo de notificaciones se corta a mitad de camino', '[22:35] jcontreras (dev): pao_qa reportó que el flujo de notificaciones se corta a mitad de camino
[22:46] jcontreras (dev): puedes mandar un ejemplo con el id del caso?
[22:48] jcontreras (dev): esto viene del último deploy o es viejo?', 'DEVCHAT-0028', '#alerts-prod', '2026-07-27T22:35:00'),
('<DEVCHAT-0010@devchat.local>', 'valen_pm@nortech.example', 'pagos está caído, nadie puede hacer login', '[20:53] valen_pm (pm): 🚨 pagos está caído, nadie puede hacer login
[21:01] root_marce (sre): pod de pagos en crashloop, viendo logs', 'DEVCHAT-0010', '#general-dev', '2026-08-01T20:53:00'),
('<DEVCHAT-0019@devchat.local>', 'pao_qa@nortech.example', 'latencia de auth-service subió como 5x desde el mediodía', '[16:02] pao_qa (qa): latencia de auth-service subió como 5x desde el mediodía
[16:07] diego.lead (lead): cpu del auth-service al 90%, parece cuello de botella
[16:13] jcontreras (dev): esto me suena a INC-2026-0006, saturación de disco en checkout
[16:25] valen_pm (pm): encontramos una query sin índice, se optimizó', 'DEVCHAT-0019', '#dev-backend', '2026-08-03T16:02:00'),
('<DEVCHAT-0007@devchat.local>', 'fely.ops@nortech.example', 'el proveedor de app-movil está devolviendo 500 hace rato', '[13:33] fely.ops (sre): el proveedor de app-movil está devolviendo 500 hace rato
[13:33] pao_qa (qa): abrí ticket con el proveedor, esperando respuesta
[13:42] pao_qa (qa): revisé el status page del proveedor, dice operativo, raro
[13:50] pao_qa (qa): esto me suena a INC-2026-0010, caída total de app-movil por pod en crashloop', 'DEVCHAT-0007', '#on-call', '2026-08-05T13:33:00'),
('<DEVCHAT-0007-seg@devchat.local>', 'pao_qa@nortech.example', 'Re: el proveedor de app-movil está devolviendo 500 hace rato', '[13:50] pao_qa (qa): esto me suena a INC-2026-0010, caída total de app-movil por pod en crashloop', 'DEVCHAT-0007', '#on-call', '2026-08-05T13:50:38'),
('<DEVCHAT-0033@devchat.local>', 'pao_qa@nortech.example', 'jcontreras dice que hay duplicados en la tabla de app-movil', '[07:00] pao_qa (qa): jcontreras dice que hay duplicados en la tabla de app-movil
[07:05] pao_qa (qa): cuántos registros están afectados?
[07:14] pao_qa (qa): esto puede haber llegado a reportes ya generados
[07:30] jcontreras (dev): se re-ejecutó el batch y se reconciliaron los datos', 'DEVCHAT-0033', '#alerts-prod', '2026-08-06T07:00:00'),
('<DEVCHAT-0003@devchat.local>', 'pao_qa@nortech.example', 'rate limit de reportes saltando constantemente', '[11:14] pao_qa (qa): rate limit de reportes saltando constantemente
[11:22] fely.ops (sre): cuánto nos queda antes de que colapse?
[11:25] bpereira (dev): esto me suena a INC-2025-0002, degradación severa de latencia en reportes', 'DEVCHAT-0003', '#general-dev', '2026-08-12T11:14:00'),
('<DEVCHAT-0029@devchat.local>', 'fely.ops@nortech.example', 'varios usuarios no pueden loguearse en login-web', '[17:35] fely.ops (sre): varios usuarios no pueden loguearse en login-web
[17:39] fely.ops (sre): es general o algún segmento en particular?
[17:40] camila.rios (dev): parece que el token expira antes de tiempo', 'DEVCHAT-0029', '#alerts-prod', '2026-08-12T17:35:00'),
('<DEVCHAT-0025@devchat.local>', 'diego.lead@nortech.example', 'rate limit de pagos saltando constantemente', '[07:31] diego.lead (lead): rate limit de pagos saltando constantemente
[07:43] diego.lead (lead): hay algo generando logs de más de lo normal?
[07:51] pao_qa (qa): cuánto nos queda antes de que colapse?
[08:04] diego.lead (lead): se aumentó el pool de conexiones', 'DEVCHAT-0025', '#on-call', '2026-08-14T07:31:00'),
('<DEVCHAT-0009@devchat.local>', 'nano_sre@nortech.example', 'rate limit de auth-service saltando constantemente', '[21:51] nano_sre (sre): rate limit de auth-service saltando constantemente
[22:02] valen_pm (pm): hay algo generando logs de más de lo normal?
[22:05] nano_sre (sre): esto me suena a INC-2026-0009, bloqueo masivo de login en reportes
[22:32] nano_sre (sre): se limpió espacio y se subió la cuota, monitoreando', 'DEVCHAT-0009', '#on-call', '2026-08-15T21:51:00'),
('<DEVCHAT-0009-seg@devchat.local>', 'nano_sre@nortech.example', 'Re: rate limit de auth-service saltando constantemente', '[22:32] nano_sre (sre): se limpió espacio y se subió la cuota, monitoreando', 'DEVCHAT-0009', '#on-call', '2026-08-15T22:32:14'),
('<DEVCHAT-0032@devchat.local>', 'diego.lead@nortech.example', 'jajaja alguien vio el video que mandé', '[14:36] diego.lead (lead): jajaja alguien vio el video que mandé
[14:45] seba_infra (sre): dale, buen finde!
[14:57] diego.lead (lead): ah ok gracias por avisar', 'DEVCHAT-0032', '#dev-backend', '2026-08-18T14:36:00'),
('<DEVCHAT-0015@devchat.local>', 'valen_pm@nortech.example', 'disco de bd-clientes al 95%, esto va a explotar', '[14:56] valen_pm (pm): disco de bd-clientes al 95%, esto va a explotar
[15:01] valen_pm (pm): hay algo generando logs de más de lo normal?
[15:28] valen_pm (pm): se aumentó el pool de conexiones', 'DEVCHAT-0015', '#alerts-prod', '2026-08-20T14:56:00'),
('<DEVCHAT-0040@devchat.local>', 'seba_infra@nortech.example', 'podemos agendar para revisar el diseño de auth-service?', '[20:31] seba_infra (sre): podemos agendar para revisar el diseño de auth-service?
[20:33] camila.rios (dev): yo tengo la doc, te la paso
[20:42] fely.ops (sre): dale, cuadremos para mañana', 'DEVCHAT-0040', '#on-call', '2026-08-22T20:31:00'),
('<DEVCHAT-0037@devchat.local>', 'root_marce@nortech.example', 'los datos de pagos están desincronizados con el origen', '[08:45] root_marce (sre): los datos de pagos están desincronizados con el origen
[08:54] jcontreras (dev): cuántos registros están afectados?
[09:03] root_marce (sre): esto me suena a INC-2025-0005, degradación severa de latencia en pagos', 'DEVCHAT-0037', '#alerts-prod', '2026-08-23T08:45:00'),
('<DEVCHAT-0020@devchat.local>', 'valen_pm@nortech.example', 'faltan registros en pagos, el batch de anoche no corrió completo', '[15:52] valen_pm (pm): faltan registros en pagos, el batch de anoche no corrió completo
[16:02] valen_pm (pm): cuántos registros están afectados?
[16:25] valen_pm (pm): se re-ejecutó el batch y se reconciliaron los datos', 'DEVCHAT-0020', '#general-dev', '2026-08-23T15:52:00'),
('<DEVCHAT-0038@devchat.local>', 'jcontreras@nortech.example', 'oye auth-service tira 502 en todos los requests, alguien más?', '[17:23] jcontreras (dev): oye auth-service tira 502 en todos los requests, alguien más?
[17:28] fely.ops (sre): confirmado, healthcheck en rojo desde las 17:23
[17:28] jcontreras (dev): lo mismo en staging o solo prod?
[17:29] jcontreras (dev): pod de auth-service en crashloop, viendo logs
[17:38] fely.ops (sre): esto me suena a INC-2026-0012, registros faltantes en pagos tras el batch nocturno', 'DEVCHAT-0038', '#alerts-prod', '2026-08-26T17:23:00'),
('<DEVCHAT-0038-seg@devchat.local>', 'fely.ops@nortech.example', 'Re: oye auth-service tira 502 en todos los requests, alguien más?', '[17:38] fely.ops (sre): esto me suena a INC-2026-0012, registros faltantes en pagos tras el batch nocturno', 'DEVCHAT-0038', '#alerts-prod', '2026-08-26T17:38:05'),
('<DEVCHAT-0016@devchat.local>', 'diego.lead@nortech.example', 'login-web está lentísimo, p95 se fue a las nubes', '[12:27] diego.lead (lead): login-web está lentísimo, p95 se fue a las nubes
[12:41] camila.rios (dev): cpu del login-web al 90%, parece cuello de botella
[12:43] root_marce (sre): cuántos usuarios afectados aprox?
[12:51] diego.lead (lead): esto me suena a INC-2025-0013, registros faltantes en login-web tras el batch nocturno
[13:12] nano_sre (sre): encontramos una query sin índice, se optimizó', 'DEVCHAT-0016', '#incidentes', '2026-08-27T12:27:00'),
('<DEVCHAT-0016-seg@devchat.local>', 'nano_sre@nortech.example', 'Re: login-web está lentísimo, p95 se fue a las nubes', '[13:12] nano_sre (sre): encontramos una query sin índice, se optimizó', 'DEVCHAT-0016', '#incidentes', '2026-08-27T13:12:11'),
('<DEVCHAT-0034@devchat.local>', 'pao_qa@nortech.example', 'oye pagos tira 502 en todos los requests, alguien más?', '[17:45] pao_qa (qa): oye pagos tira 502 en todos los requests, alguien más?
[17:59] fely.ops (sre): clientes ya están reclamando por redes sociales
[18:12] pao_qa (qa): confirmado, healthcheck en rojo desde las 17:45
[18:16] diego.lead (lead): pod de pagos en crashloop, viendo logs
[18:46] root_marce (sre): se reinició el pod y volvió, quedamos atentos', 'DEVCHAT-0034', '#incidentes', '2026-08-30T17:45:00'),
('<DEVCHAT-0034-seg@devchat.local>', 'root_marce@nortech.example', 'Re: oye pagos tira 502 en todos los requests, alguien más?', '[18:46] root_marce (sre): se reinició el pod y volvió, quedamos atentos', 'DEVCHAT-0034', '#incidentes', '2026-08-30T18:46:11')
) as v(mid, remitente, asunto, cuerpo, thread_id, canal, recibido_en)
on conflict (id) do nothing;

-- ------------------------------------------------------------
-- 2) Incidentes de los hilos marcados como incidente (31)
--
-- causa_raiz_real y solucion_esperada son la verdad de referencia; la vista
-- incidentes_agente no las expone. Quedan nulas cuando el hilo no dice la causa.
-- logs_adjuntos lleva los mensajes del hilo, citables uno a uno.
-- ------------------------------------------------------------
insert into incidentes (
  id, ticket_numero, titulo, descripcion, tipo_problema, severidad, sistema_afectado,
  estado, dificultad, canal_origen, origen_email_id, causa_raiz_real, solucion_esperada,
  logs_adjuntos, creado_en
)
select
  md5('inc:' || v.mid)::uuid,
  v.ticket,
  v.titulo,
  e.cuerpo,
  v.tipo,
  v.severidad,
  v.sistema,
  v.estado,
  v.dificultad,
  'email',
  e.id,
  v.causa_raiz,
  v.solucion,
  v.logs::jsonb,
  e.recibido_en + interval '12 minutes'
from (values
('<DEVCHAT-0002@devchat.local>', 'INC-0001', 'oye cola-mensajes tira 502 en todos los requests, alguien más?', 'indisponibilidad', 'media', 'cola-mensajes', 'resuelto', 'dificil', 'era un deploy mal aplicado, se hizo rollback y ya volvió', 'era un deploy mal aplicado, se hizo rollback y ya volvió', '["2026-07-16T18:01:00 seba_infra: oye cola-mensajes tira 502 en todos los requests, alguien más?", "2026-07-16T18:09:55 seba_infra: lo mismo en staging o solo prod?", "2026-07-16T18:14:08 diego.lead: pod de cola-mensajes en crashloop, viendo logs", "2026-07-16T18:16:50 jcontreras: confirmado, healthcheck en rojo desde las 18:01", "2026-07-16T18:25:48 seba_infra: esto me suena a INC-2026-0007, cálculo incorrecto en notificaciones para montos negativos", "2026-07-16T18:41:30 jcontreras: era un deploy mal aplicado, se hizo rollback y ya volvió"]'),
('<DEVCHAT-0003@devchat.local>', 'INC-0002', 'rate limit de reportes saltando constantemente', 'capacidad', 'media', 'reportes', 'abierto', 'facil', 'query sin índice tras una migración', 'se agregó índice y se optimizó la query', '["2026-08-12T11:14:00 pao_qa: rate limit de reportes saltando constantemente", "2026-08-12T11:22:46 fely.ops: cuánto nos queda antes de que colapse?", "2026-08-12T11:25:45 bpereira: esto me suena a INC-2025-0002, degradación severa de latencia en reportes"]'),
('<DEVCHAT-0005@devchat.local>', 'INC-0003', 'checkout está caído, nadie puede hacer login', 'indisponibilidad', 'alta', 'checkout', 'resuelto', 'dificil', 'era un deploy mal aplicado, se hizo rollback y ya volvió', 'era un deploy mal aplicado, se hizo rollback y ya volvió', '["2026-06-17T07:04:00 nano_sre: 🚨 checkout está caído, nadie puede hacer login", "2026-06-17T07:14:46 camila.rios: lo mismo en staging o solo prod?", "2026-06-17T07:23:21 nano_sre: pod de checkout en crashloop, viendo logs", "2026-06-17T07:25:49 seba_infra: clientes ya están reclamando por redes sociales", "2026-06-17T07:34:16 seba_infra: confirmado, healthcheck en rojo desde las 07:04", "2026-06-17T07:39:45 camila.rios: era un deploy mal aplicado, se hizo rollback y ya volvió"]'),
('<DEVCHAT-0007@devchat.local>', 'INC-0004', 'el proveedor de app-movil está devolviendo 500 hace rato', 'integracion_terceros', 'alta', 'app-movil', 'en_progreso', 'medio', 'deploy con configuración inválida', 'rollback al release anterior', '["2026-08-05T13:33:00 fely.ops: el proveedor de app-movil está devolviendo 500 hace rato", "2026-08-05T13:33:58 pao_qa: abrí ticket con el proveedor, esperando respuesta", "2026-08-05T13:42:31 pao_qa: revisé el status page del proveedor, dice operativo, raro", "2026-08-05T13:50:38 pao_qa: esto me suena a INC-2026-0010, caída total de app-movil por pod en crashloop"]'),
('<DEVCHAT-0008@devchat.local>', 'INC-0005', 'bpereira reportó que el flujo de batch-facturacion se corta a mitad de camino', 'error_funcional', 'baja', 'batch-facturacion', 'resuelto', 'facil', 'era un edge case con montos negativos, el fix ya está en review', 'era un edge case con montos negativos, el fix ya está en review', '["2026-07-21T09:53:00 seba_infra: bpereira reportó que el flujo de batch-facturacion se corta a mitad de camino", "2026-07-21T10:06:51 bpereira: reproduje en staging, es el mismo comportamiento", "2026-07-21T10:35:47 diego.lead: era un edge case con montos negativos, el fix ya está en review"]'),
('<DEVCHAT-0009@devchat.local>', 'INC-0006', 'rate limit de auth-service saltando constantemente', 'capacidad', 'media', 'auth-service', 'resuelto', 'medio', 'se limpió espacio y se subió la cuota, monitoreando', 'se limpió espacio y se subió la cuota, monitoreando', '["2026-08-15T21:51:00 nano_sre: rate limit de auth-service saltando constantemente", "2026-08-15T22:02:43 valen_pm: hay algo generando logs de más de lo normal?", "2026-08-15T22:05:27 nano_sre: esto me suena a INC-2026-0009, bloqueo masivo de login en reportes", "2026-08-15T22:32:14 nano_sre: se limpió espacio y se subió la cuota, monitoreando"]'),
('<DEVCHAT-0010@devchat.local>', 'INC-0007', 'pagos está caído, nadie puede hacer login', 'indisponibilidad', 'alta', 'pagos', 'abierto', 'facil', null, null, '["2026-08-01T20:53:00 valen_pm: 🚨 pagos está caído, nadie puede hacer login", "2026-08-01T21:01:19 root_marce: pod de pagos en crashloop, viendo logs"]'),
('<DEVCHAT-0011@devchat.local>', 'INC-0008', 'login-web está lentísimo, p95 se fue a las nubes', 'degradacion', 'baja', 'login-web', 'resuelto', 'facil', 'se escaló el número de réplicas y bajó la latencia', 'se escaló el número de réplicas y bajó la latencia', '["2026-06-18T07:49:00 diego.lead: login-web está lentísimo, p95 se fue a las nubes", "2026-06-18T07:57:34 diego.lead: cpu del login-web al 90%, parece cuello de botella", "2026-06-18T08:17:15 nano_sre: se escaló el número de réplicas y bajó la latencia"]'),
('<DEVCHAT-0012@devchat.local>', 'INC-0009', 'rate limit de login-web saltando constantemente', 'capacidad', 'baja', 'login-web', 'abierto', 'facil', null, null, '["2026-07-09T17:39:00 valen_pm: rate limit de login-web saltando constantemente", "2026-07-09T17:47:13 camila.rios: hay algo generando logs de más de lo normal?"]'),
('<DEVCHAT-0014@devchat.local>', 'INC-0010', 'api-gateway está lentísimo, p95 se fue a las nubes', 'degradacion', 'media', 'api-gateway', 'resuelto', 'facil', 'se escaló el número de réplicas y bajó la latencia', 'se escaló el número de réplicas y bajó la latencia', '["2026-07-03T12:42:00 fely.ops: api-gateway está lentísimo, p95 se fue a las nubes", "2026-07-03T12:49:51 pao_qa: cuántos usuarios afectados aprox?", "2026-07-03T13:04:01 camila.rios: se escaló el número de réplicas y bajó la latencia"]'),
('<DEVCHAT-0015@devchat.local>', 'INC-0011', 'disco de bd-clientes al 95%, esto va a explotar', 'capacidad', 'baja', 'bd-clientes', 'resuelto', 'facil', 'se aumentó el pool de conexiones', 'se aumentó el pool de conexiones', '["2026-08-20T14:56:00 valen_pm: disco de bd-clientes al 95%, esto va a explotar", "2026-08-20T15:01:08 valen_pm: hay algo generando logs de más de lo normal?", "2026-08-20T15:28:55 valen_pm: se aumentó el pool de conexiones"]'),
('<DEVCHAT-0016@devchat.local>', 'INC-0012', 'login-web está lentísimo, p95 se fue a las nubes', 'degradacion', 'media', 'login-web', 'resuelto', 'medio', 'encontramos una query sin índice, se optimizó', 'encontramos una query sin índice, se optimizó', '["2026-08-27T12:27:00 diego.lead: login-web está lentísimo, p95 se fue a las nubes", "2026-08-27T12:41:10 camila.rios: cpu del login-web al 90%, parece cuello de botella", "2026-08-27T12:43:05 root_marce: cuántos usuarios afectados aprox?", "2026-08-27T12:51:19 diego.lead: esto me suena a INC-2025-0013, registros faltantes en login-web tras el batch nocturno", "2026-08-27T13:12:11 nano_sre: encontramos una query sin índice, se optimizó"]'),
('<DEVCHAT-0018@devchat.local>', 'INC-0013', 'cola-mensajes no responde desde hace como 10 min', 'indisponibilidad', 'critica', 'cola-mensajes', 'en_progreso', 'medio', null, null, '["2026-07-08T10:42:00 valen_pm: cola-mensajes no responde desde hace como 10 min", "2026-07-08T10:54:14 fely.ops: clientes ya están reclamando por redes sociales", "2026-07-08T10:58:39 diego.lead: pod de cola-mensajes en crashloop, viendo logs", "2026-07-08T11:02:32 fely.ops: lo mismo en staging o solo prod?", "2026-07-08T11:09:56 diego.lead: confirmado, healthcheck en rojo desde las 10:42"]'),
('<DEVCHAT-0019@devchat.local>', 'INC-0014', 'latencia de auth-service subió como 5x desde el mediodía', 'degradacion', 'alta', 'auth-service', 'resuelto', 'medio', 'encontramos una query sin índice, se optimizó', 'encontramos una query sin índice, se optimizó', '["2026-08-03T16:02:00 pao_qa: latencia de auth-service subió como 5x desde el mediodía", "2026-08-03T16:07:05 diego.lead: cpu del auth-service al 90%, parece cuello de botella", "2026-08-03T16:13:11 jcontreras: esto me suena a INC-2026-0006, saturación de disco en checkout", "2026-08-03T16:25:44 valen_pm: encontramos una query sin índice, se optimizó"]'),
('<DEVCHAT-0020@devchat.local>', 'INC-0015', 'faltan registros en pagos, el batch de anoche no corrió completo', 'datos', 'media', 'pagos', 'resuelto', 'facil', 'se re-ejecutó el batch y se reconciliaron los datos', 'se re-ejecutó el batch y se reconciliaron los datos', '["2026-08-23T15:52:00 valen_pm: faltan registros en pagos, el batch de anoche no corrió completo", "2026-08-23T16:02:30 valen_pm: cuántos registros están afectados?", "2026-08-23T16:25:59 valen_pm: se re-ejecutó el batch y se reconciliaron los datos"]'),
('<DEVCHAT-0021@devchat.local>', 'INC-0016', 'nano_sre reportó que el flujo de reportes se corta a mitad de camino', 'error_funcional', 'alta', 'reportes', 'resuelto', 'dificil', 'era un edge case con montos negativos, el fix ya está en review', 'era un edge case con montos negativos, el fix ya está en review', '["2026-06-16T11:02:00 diego.lead: nano_sre reportó que el flujo de reportes se corta a mitad de camino", "2026-06-16T11:11:26 diego.lead: esto viene del último deploy o es viejo?", "2026-06-16T11:26:02 nano_sre: reproduje en staging, es el mismo comportamiento", "2026-06-16T11:27:59 diego.lead: puedes mandar un ejemplo con el id del caso?", "2026-06-16T11:34:38 diego.lead: esto me suena a INC-2026-0011, saturación de disco en reportes", "2026-06-16T11:52:02 diego.lead: era un edge case con montos negativos, el fix ya está en review"]'),
('<DEVCHAT-0022@devchat.local>', 'INC-0017', 'tengo tickets de gente bloqueada después del reset de clave', 'acceso_identidad', 'alta', 'auth-service', 'en_progreso', 'medio', 'logs de debug dejados activos en producción', 'se desactivó el log verboso y se amplió cuota', '["2026-06-28T09:47:00 valen_pm: tengo tickets de gente bloqueada después del reset de clave", "2026-06-28T10:01:56 camila.rios: parece que el token expira antes de tiempo", "2026-06-28T10:06:26 seba_infra: es general o algún segmento en particular?", "2026-06-28T10:14:47 root_marce: esto me suena a INC-2026-0011, saturación de disco en reportes"]'),
('<DEVCHAT-0023@devchat.local>', 'INC-0018', 'webhook de cache-redis dejó de llegar', 'integracion_terceros', 'alta', 'cache-redis', 'en_progreso', 'medio', null, null, '["2026-07-23T15:41:00 camila.rios: webhook de cache-redis dejó de llegar", "2026-07-23T15:49:43 camila.rios: puede ser rate limit de nuestro lado", "2026-07-23T15:58:30 nano_sre: revisé el status page del proveedor, dice operativo, raro", "2026-07-23T16:10:28 camila.rios: abrí ticket con el proveedor, esperando respuesta"]'),
('<DEVCHAT-0024@devchat.local>', 'INC-0019', 'nos estamos quedando sin conexiones en el pool de login-web', 'capacidad', 'alta', 'login-web', 'resuelto', 'medio', 'se aumentó el pool de conexiones', 'se aumentó el pool de conexiones', '["2026-07-05T07:18:00 jcontreras: nos estamos quedando sin conexiones en el pool de login-web", "2026-07-05T07:23:05 camila.rios: hay algo generando logs de más de lo normal?", "2026-07-05T07:24:51 jcontreras: esto me suena a INC-2025-0013, registros faltantes en login-web tras el batch nocturno", "2026-07-05T07:44:44 camila.rios: se aumentó el pool de conexiones"]'),
('<DEVCHAT-0025@devchat.local>', 'INC-0020', 'rate limit de pagos saltando constantemente', 'capacidad', 'baja', 'pagos', 'resuelto', 'medio', 'se aumentó el pool de conexiones', 'se aumentó el pool de conexiones', '["2026-08-14T07:31:00 diego.lead: rate limit de pagos saltando constantemente", "2026-08-14T07:43:54 diego.lead: hay algo generando logs de más de lo normal?", "2026-08-14T07:51:30 pao_qa: cuánto nos queda antes de que colapse?", "2026-08-14T08:04:48 diego.lead: se aumentó el pool de conexiones"]'),
('<DEVCHAT-0026@devchat.local>', 'INC-0021', 'rate limit de cola-mensajes saltando constantemente', 'capacidad', 'media', 'cola-mensajes', 'resuelto', 'facil', 'se aumentó el pool de conexiones', 'se aumentó el pool de conexiones', '["2026-07-15T19:55:00 jcontreras: rate limit de cola-mensajes saltando constantemente", "2026-07-15T20:02:48 root_marce: hay algo generando logs de más de lo normal?", "2026-07-15T20:06:33 camila.rios: se aumentó el pool de conexiones"]'),
('<DEVCHAT-0027@devchat.local>', 'INC-0022', 'faltan registros en pagos, el batch de anoche no corrió completo', 'datos', 'baja', 'pagos', 'resuelto', 'facil', 'se re-ejecutó el batch y se reconciliaron los datos', 'se re-ejecutó el batch y se reconciliaron los datos', '["2026-06-25T13:46:00 pao_qa: faltan registros en pagos, el batch de anoche no corrió completo", "2026-06-25T13:53:30 bpereira: esto puede haber llegado a reportes ya generados", "2026-06-25T14:05:16 bpereira: se re-ejecutó el batch y se reconciliaron los datos"]'),
('<DEVCHAT-0028@devchat.local>', 'INC-0023', 'pao_qa reportó que el flujo de notificaciones se corta a mitad de camino', 'error_funcional', 'alta', 'notificaciones', 'abierto', 'facil', null, null, '["2026-07-27T22:35:00 jcontreras: pao_qa reportó que el flujo de notificaciones se corta a mitad de camino", "2026-07-27T22:46:28 jcontreras: puedes mandar un ejemplo con el id del caso?", "2026-07-27T22:48:14 jcontreras: esto viene del último deploy o es viejo?"]'),
('<DEVCHAT-0029@devchat.local>', 'INC-0024', 'varios usuarios no pueden loguearse en login-web', 'acceso_identidad', 'alta', 'login-web', 'abierto', 'facil', null, null, '["2026-08-12T17:35:00 fely.ops: varios usuarios no pueden loguearse en login-web", "2026-08-12T17:39:54 fely.ops: es general o algún segmento en particular?", "2026-08-12T17:40:44 camila.rios: parece que el token expira antes de tiempo"]'),
('<DEVCHAT-0030@devchat.local>', 'INC-0025', 'encontré un bug en reportes, el descuento no se aplica bien', 'error_funcional', 'media', 'reportes', 'resuelto', 'facil', 'era un edge case con montos negativos, el fix ya está en review', 'era un edge case con montos negativos, el fix ya está en review', '["2026-06-15T13:05:00 valen_pm: encontré un bug en reportes, el descuento no se aplica bien", "2026-06-15T13:12:19 seba_infra: reproduje en staging, es el mismo comportamiento", "2026-06-15T13:42:06 valen_pm: era un edge case con montos negativos, el fix ya está en review"]'),
('<DEVCHAT-0033@devchat.local>', 'INC-0026', 'jcontreras dice que hay duplicados en la tabla de app-movil', 'datos', 'alta', 'app-movil', 'resuelto', 'medio', 'se re-ejecutó el batch y se reconciliaron los datos', 'se re-ejecutó el batch y se reconciliaron los datos', '["2026-08-06T07:00:00 pao_qa: jcontreras dice que hay duplicados en la tabla de app-movil", "2026-08-06T07:05:53 pao_qa: cuántos registros están afectados?", "2026-08-06T07:14:29 pao_qa: esto puede haber llegado a reportes ya generados", "2026-08-06T07:30:32 jcontreras: se re-ejecutó el batch y se reconciliaron los datos"]'),
('<DEVCHAT-0034@devchat.local>', 'INC-0027', 'oye pagos tira 502 en todos los requests, alguien más?', 'indisponibilidad', 'alta', 'pagos', 'resuelto', 'medio', 'se reinició el pod y volvió, quedamos atentos', 'se reinició el pod y volvió, quedamos atentos', '["2026-08-30T17:45:00 pao_qa: oye pagos tira 502 en todos los requests, alguien más?", "2026-08-30T17:59:06 fely.ops: clientes ya están reclamando por redes sociales", "2026-08-30T18:12:12 pao_qa: confirmado, healthcheck en rojo desde las 17:45", "2026-08-30T18:16:12 diego.lead: pod de pagos en crashloop, viendo logs", "2026-08-30T18:46:11 root_marce: se reinició el pod y volvió, quedamos atentos"]'),
('<DEVCHAT-0036@devchat.local>', 'INC-0028', 'seba_infra reportó que el flujo de cola-mensajes se corta a mitad de camino', 'error_funcional', 'media', 'cola-mensajes', 'resuelto', 'medio', 'era un edge case con montos negativos, el fix ya está en review', 'era un edge case con montos negativos, el fix ya está en review', '["2026-07-23T13:11:00 camila.rios: seba_infra reportó que el flujo de cola-mensajes se corta a mitad de camino", "2026-07-23T13:16:49 nano_sre: esto viene del último deploy o es viejo?", "2026-07-23T13:29:41 seba_infra: reproduje en staging, es el mismo comportamiento", "2026-07-23T13:44:30 seba_infra: puedes mandar un ejemplo con el id del caso?", "2026-07-23T13:50:13 camila.rios: era un edge case con montos negativos, el fix ya está en review"]'),
('<DEVCHAT-0037@devchat.local>', 'INC-0029', 'los datos de pagos están desincronizados con el origen', 'datos', 'media', 'pagos', 'abierto', 'facil', 'query sin índice tras una migración', 'se agregó índice y se optimizó la query', '["2026-08-23T08:45:00 root_marce: los datos de pagos están desincronizados con el origen", "2026-08-23T08:54:44 jcontreras: cuántos registros están afectados?", "2026-08-23T09:03:19 root_marce: esto me suena a INC-2025-0005, degradación severa de latencia en pagos"]'),
('<DEVCHAT-0038@devchat.local>', 'INC-0030', 'oye auth-service tira 502 en todos los requests, alguien más?', 'indisponibilidad', 'media', 'auth-service', 'en_progreso', 'medio', 'fallo silencioso del job de sincronización', 'se agregó alertamiento al job y reconciliación manual', '["2026-08-26T17:23:00 jcontreras: oye auth-service tira 502 en todos los requests, alguien más?", "2026-08-26T17:28:12 fely.ops: confirmado, healthcheck en rojo desde las 17:23", "2026-08-26T17:28:45 jcontreras: lo mismo en staging o solo prod?", "2026-08-26T17:29:39 jcontreras: pod de auth-service en crashloop, viendo logs", "2026-08-26T17:38:05 fely.ops: esto me suena a INC-2026-0012, registros faltantes en pagos tras el batch nocturno"]'),
('<DEVCHAT-0039@devchat.local>', 'INC-0031', 'usuarios reportando que tarda una eternidad en cargar', 'degradacion', 'media', 'cola-mensajes', 'resuelto', 'facil', 'se escaló el número de réplicas y bajó la latencia', 'se escaló el número de réplicas y bajó la latencia', '["2026-07-25T21:23:00 nano_sre: usuarios reportando que tarda una eternidad en cargar", "2026-07-25T21:26:52 fely.ops: cuántos usuarios afectados aprox?", "2026-07-25T21:31:04 root_marce: se escaló el número de réplicas y bajó la latencia"]')
) as v(mid, ticket, titulo, tipo, severidad, sistema, estado, dificultad, causa_raiz, solucion, logs)
join emails_entrantes e on e.id = md5(v.mid)::uuid
on conflict (id) do nothing;

-- ------------------------------------------------------------
-- 3) Cerrar el circulo en los correos entrantes
-- ------------------------------------------------------------

-- Los que derivaron en ticket quedan enlazados.
update emails_entrantes e
set procesado = true,
    procesado_en = i.creado_en,
    incidente_id = i.id
from incidentes i
where i.origen_email_id = e.id
  and e.incidente_id is null;

-- El resto queda procesado y sin incidente: se evaluo y se descarto.
update emails_entrantes
set procesado = true,
    procesado_en = recibido_en + interval '20 minutes'
where headers->>'X-Seed' = 'devchat'
  and incidente_id is null
  and procesado = false;

-- ------------------------------------------------------------
-- 4) Borradores de respuesta para los incidentes ya atendidos
-- ------------------------------------------------------------
insert into emails_salientes (id, incidente_id, destinatario, asunto, cuerpo, estado, creado_en)
select
  md5('out:' || e.message_id)::uuid,
  i.id,
  e.remitente,
  '[' || i.ticket_numero || '] ' || i.titulo,
  'Hola,' || chr(10) || chr(10) ||
  'Registramos tu reporte como ' || i.ticket_numero || ' (' || i.severidad || ', ' || i.sistema_afectado || ').' || chr(10) ||
  'Estado actual: ' || i.estado || '.' || chr(10) || chr(10) ||
  'Te escribimos apenas haya novedades.' || chr(10) || chr(10) ||
  'Equipo de Soporte',
  'borrador',
  i.creado_en + interval '35 minutes'
from incidentes i
join emails_entrantes e on e.id = i.origen_email_id
where i.estado in ('en_progreso', 'resuelto')
on conflict (id) do nothing;

-- ------------------------------------------------------------
-- 5) Dejar la secuencia despues de los tickets del seed
-- ------------------------------------------------------------
select setval('incidentes_numero_seq', 31, true);
