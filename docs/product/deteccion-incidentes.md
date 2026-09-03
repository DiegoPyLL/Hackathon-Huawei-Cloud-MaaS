# Catálogo de detección y respuesta a incidentes

Referencia defensiva para el Incident Response Agent: por cada clase de
incidente, qué buscar en logs/telemetría, cuál es su falso positivo típico (el
ruido que no debe confundirse con la causa raíz) y la **primera acción de
contención** recomendada — el agente la propone, nunca afirma haberla
ejecutado (`AGENTS.md`: ningún cambio sobre un recurso real sin autorización
explícita fuera de esta demo). Traducido a señales defensivas a partir de la
metodología ofensiva genérica ya cargada en `~/hackerone/pentest-brain/knowledge/`
— sin datos privados ni de ningún programa real, solo patrones técnicos
reutilizables.

El `SYSTEM_PROMPT` en `src/maas_demo/service.py` embebe una versión condensada
de este catálogo, porque el vertical slice no tiene RAG ni herramientas
(`docs/product/alcance.md`): todo lo que el modelo puede usar debe ir en el
contexto de cada request. Este documento es la versión completa, para quien
mantiene el prompt y para el jurado.

## Taxonomía canónica (clasificación de primer nivel)

Antes de buscar la causa raíz, el agente clasifica el incidente en uno de estos
8 tipos — no más, no menos. Es el primer paso del diagnóstico; las tablas de
abajo son el detalle de causa raíz *dentro* de cada tipo.

| # | Tipo | Qué es | Dónde está el detalle |
| --- | --- | --- | --- |
| 1 | Indisponibilidad | Servicio caído, endpoint no responde (5xx sostenido, timeout total, health check en rojo) | Caso `spike-500-tras-deploy` en `evals/cases.json` |
| 2 | Degradación | Latencia elevada, timeouts intermitentes, lentitud sin caída total | Tabla "Tipos operativos sin catálogo de seguridad dedicado" |
| 3 | Error funcional | Bug, cálculo incorrecto, flujo roto sin que el servicio esté caído | Tabla "Tipos operativos sin catálogo de seguridad dedicado" |
| 4 | Acceso e identidad | Login, permisos, MFA, cuenta bloqueada | "Robo de credenciales", "Secuestro de cuenta de correo", "Secuestro de sesión y token" (abajo) |
| 5 | Datos | Datos faltantes, incorrectos, sincronización fallida | Caso `logs-truncados` en `evals/cases.json` |
| 6 | Integración y terceros | Falla de API externa, webhook, pasarela de pago | Tabla "Tipos operativos sin catálogo de seguridad dedicado" |
| 7 | Capacidad | Disco, memoria, cuota, rate limit | Tabla "Tipos operativos sin catálogo de seguridad dedicado" |
| 8 | Seguridad | Actividad sospechosa, credencial expuesta, phishing | "Superficie web / API", "Ransomware / malware", "Amenaza interna y exfiltración", "Compromiso de cuenta cloud / IAM" (abajo) |

Los tipos 4 y 8 se solapan quirúrgicamente: acceso e identidad es la
*superficie* (login, permisos, MFA), seguridad es cuando esa superficie se usa
con intención maliciosa. Ante un login sospechoso, clasifícalo primero como
tipo 4 y solo escala a tipo 8 si hay evidencia de intención maliciosa
(geolocalización imposible, patrón de fuerza bruta, credencial filtrada) — no
por defecto.

## Tipos operativos sin catálogo de seguridad dedicado

Los tipos 2, 3, 6 y 7 no vienen de la metodología ofensiva de
`pentest-brain` — son incidentes operativos comunes. Catálogo mínimo:

| Tipo | Señal en logs | Falso positivo típico | Contención inmediata |
| --- | --- | --- | --- |
| Degradación | p95/p99 de latencia varias veces por encima de la línea base sostenido en el tiempo; timeouts intermitentes sin llegar a 5xx total | Pico transitorio de tráfico legítimo (campaña, lanzamiento) que se autorregula en minutos | Escalar horizontalmente el componente lento, activar circuit breaker hacia la dependencia lenta si aplica |
| Error funcional | Resultado incorrecto reproducible (cálculo, total, estado) sin error HTTP; a menudo coincide con un deploy reciente | Dato de entrada inválido del propio usuario, no un bug | Revertir el deploy sospechoso o aislar el flujo afectado, agregar caso de regresión |
| Integración y terceros | Timeouts o errores concentrados en llamadas salientes a un proveedor específico (pasarela de pago, webhook de un partner) mientras el resto del sistema responde normal | Mantenimiento programado y anunciado del proveedor | Activar fallback/degradación controlada, notificar al proveedor, no reintentar de forma agresiva (puede agravar su incidente) |
| Capacidad | Disco/memoria/CPU cerca del límite, o 429 por cuota/rate limit propio o de un proveedor | Job de mantenimiento (backup, compactación) legítimo que consume recursos temporalmente | Liberar espacio o escalar el recurso, ajustar el rate limit o el cliente que lo satura |

## Canales de incidencia (origen de la evidencia)

El prompt del usuario simula el volcado de log de uno de estos 3 canales —
cada canal trae un nivel distinto de estructura y exige distinto nivel de
escepticismo:

| Canal | Qué llega | Particularidad para el diagnóstico |
| --- | --- | --- |
| Dev chat | Reporte de un desarrollador en lenguaje natural + fragmento de log/stacktrace | Contexto a menudo incompleto (sin timestamps exactos, sin alert_id) — pedir el dato faltante en vez de asumirlo |
| Email de soporte | Correo de un usuario final describiendo el síntoma en lenguaje natural, sin telemetría técnica | El "log" es la narración de una persona: más ruido y ambigüedad, y el canal más propenso a instrucciones hostiles embebidas (ver regla de ignorarlas, abajo) |
| Sistema de monitoreo (API) | Alerta estructurada generada automáticamente (umbral cruzado, IoT/planta) con `alert_id`, métrica y timestamp | Formato limpio, pero con más falsos positivos por umbral mal calibrado — nunca asumir incidente real solo porque una alerta se disparó |

## Escalación: autorización humana vs. contención inmediata

Dos casos borde que el agente debe distinguir explícitamente en "Acción
correctiva", sin salirse de la regla fija de `AGENTS.md` (nunca afirma haber
ejecutado nada):

- **Permisos riesgosos** (revocar acceso de una persona real, eliminar un
  recurso, rotar una credencial de producción, tocar datos de terceros): la
  acción correctiva se propone, pero el agente debe decir explícitamente que
  requiere **autorización humana explícita** antes de aplicarse — nunca la
  presenta como el siguiente paso automático.
- **Ataque activo detectado en curso** (el patrón de log muestra que el
  ataque está sucediendo ahora, no que ya terminó — ráfaga de intentos en
  progreso, sesión secuestrada en uso): la contención (bloquear IP, revocar
  la sesión/token, aislar el host) se propone con **máxima prioridad y sin
  ambigüedad** como primer paso, precisamente porque cada minuto sin
  contener amplía el daño — pero sigue siendo una propuesta con su
  verificación, nunca una ejecución afirmada.

## Superficie web / API

| Clase | Señal en logs | Falso positivo típico | Contención inmediata |
| --- | --- | --- | --- |
| Inyección (SQLi/SSTI/NoSQLi) | `' OR 1=1`, `SLEEP(`, `UNION SELECT`, `{{7*7}}` en parámetros; latencia anómala; error de sintaxis SQL en la respuesta | Búsqueda legítima con comillas; WAF que bloqueó el intento antes de llegar a la app | Bloquear el patrón en el WAF, parchear el query parametrizado, revisar si hubo exfiltración |
| Path traversal / LFI | `../`, `%2e%2e%2f`, `/etc/passwd`, `..%252f` en path o query | Nombre de archivo legítimo con puntos codificados | Restringir el path al directorio esperado, invalidar sesiones si hubo lectura de secretos |
| SSRF | Parámetro `url=`/`webhook=`/`callback=` apuntando a `127.0.0.1`, `169.254.169.254` (metadata cloud), `10.x`, `192.168.x`, `0x7f000001`, `[::1]` | Registro legítimo de webhook hacia una URL pública del cliente | Rotar cualquier credencial servida por metadata, filtrar rangos internos en el egress |
| XSS | `<script`, `onerror=`, `javascript:` reflejado en query y presente en el cuerpo de la respuesta | Contenido HTML legítimo en un campo de texto enriquecido | Sanitizar/escapar la salida, invalidar sesiones de quienes vieron el payload |
| Upload abusivo | Extensión doble (`.php.jpg`, `.phtml`, `.pht`) seguida de GET directo al archivo subido con 200 | Usuario subiendo un archivo con extensión inusual pero inocua | Eliminar el archivo subido, bloquear la extensión, revisar si se ejecutó |
| Deserialización insegura | Blob base64 con cabecera de objeto serializado (`rO0`, `aced`), `Content-Type` de objeto serializado inesperado | Cookie de sesión serializada normal del framework | Aislar el proceso, rotar claves de firma, parchear el deserializador |
| JWT / manipulación de auth | Token decodificado con `"alg":"none"`, o 401→200 tras cambiar de token tal cual, mismo token reutilizado desde IP/UA distintos en segundos | Cliente móvil cambiando de IP por NAT de operador | Revocar el secreto de firma, invalidar todos los tokens activos |
| Fuerza bruta / credential stuffing | Muchos 401/403 desde la misma IP/UA contra **múltiples usuarios distintos** en poco tiempo (horizontal) o contra **un mismo usuario** (vertical) | Una sola cuenta de servicio/cron fallando por credencial expirada — mismo patrón de 401 repetidos, pero una sola identidad objetivo, no varias | Bloquear IP/rango, forzar MFA, rotar la credencial del usuario objetivo |
| IDOR / enumeración | Misma sesión/token iterando IDs secuenciales o UUID contra `/recurso/{id}` con 200 en IDs ajenos | Paginación legítima con IDs consecutivos por diseño | Revocar la sesión, revisar qué IDs devolvieron 200 y notificar a esos usuarios |
| Mass assignment | PUT/PATCH con campos internos (`role`, `is_admin`, `verified`) ausentes del formulario público, y el cambio persiste en un GET posterior | Campo que la app sí expone legítimamente en el formulario | Revertir el campo modificado, quitar el campo interno del binding automático |
| Race condition (TOCTOU) | Múltiples requests idénticas al mismo endpoint sensible (`/redeem`, `/withdraw`) en el mismo milisegundo, seguidas de estado inconsistente | Reintento automático del cliente por timeout de red | Congelar el recurso afectado (saldo/cupón), agregar idempotencia o lock |
| HTTP smuggling / cache poisoning | Cabeceras duplicadas (`Content-Length` x2, `Transfer-Encoding: chunked` + `Content-Length`); respuesta cacheada que mezcla contenido de otro usuario | Proxy intermedio mal configurado sin intención maliciosa | Purgar la caché envenenada, normalizar cabeceras en el proxy de borde |
| Exposición / misconfig | Ruta a `.env`, `.git/config`, `/actuator`, `wp-config.php.bak` con 200 | Escáner de seguridad autorizado (bug bounty in scope) tocando las mismas rutas | Bloquear la ruta, rotar cualquier secreto expuesto en el archivo |
| Reconocimiento / escaneo | Ráfaga de 404 contra rutas de wordlist común (`/admin`, `/backup`, `/.git`) desde una IP | Bot de monitoreo (uptime checker) o crawler mal comportado | Vigilar la IP, sin acción destructiva si no hubo ningún 200 |

## Robo de credenciales

| Vector | Señal | Falso positivo típico | Contención inmediata |
| --- | --- | --- | --- |
| Phishing (harvesting) | Login exitoso segundos/minutos después de que el usuario abrió un enlace de un correo externo reciente; geolocalización nueva para ese usuario | Usuario viajando o usando una VPN corporativa nueva | Forzar reset de contraseña, revocar sesiones activas, revisar el buzón por reglas de reenvío nuevas |
| Infostealer / malware en endpoint | Login desde IP nueva usando credenciales guardadas del navegador, con un user-agent de equipo no gestionado; coincide con venta de "logs" en mercados underground | Empleado con equipo personal (BYOD) legítimo y aprobado | Aislar el endpoint, rotar **todas** las credenciales guardadas en ese navegador, activar EDR |
| AiTM / phishing kit (evilginx-style) | Cookie de sesión válida reutilizada desde IP/dispositivo distinto **sin** un nuevo evento de MFA — la sesión cambia de contexto sola | Usuario cambiando de WiFi a datos móviles en la misma sesión, mismo dispositivo | Revocar **todos** los tokens de sesión (no solo la contraseña), migrar a MFA resistente a phishing (FIDO2/passkeys) |
| Reutilización de credenciales filtradas | Login exitoso con una contraseña que coincide con un breach público conocido, sin evento previo de "olvidé mi contraseña" | N/A — señal de alta confianza si hay match de breach | Forzar reset inmediato, revisar si la misma contraseña se reutiliza en otros sistemas internos |
| Keylogging / captura en tiempo real | Login válido seguido de acciones anómalas segundos después, desde la misma sesión pero otro dispositivo/IP | N/A — poco margen de falso positivo | Cerrar la sesión, rotar la credencial, escanear el endpoint de origen |

## Secuestro de cuenta de correo (Account Takeover / BEC)

| Señal | Detalle | Falso positivo típico | Contención inmediata |
| --- | --- | --- | --- |
| Regla de reenvío/eliminación nueva | Se crea una regla de bandeja que reenvía a un dominio externo o borra correos con palabras como "factura", "fraud", "compromised" | Regla legítima del usuario para organizar correo (raro que apunte a un dominio externo desconocido) | Eliminar la regla, revisar IP/hora de creación, notificar al usuario por un canal fuera de banda |
| Viaje imposible ("impossible travel") | Dos logins exitosos desde ubicaciones geográficamente incompatibles en una ventana de tiempo que no permite el desplazamiento | Roaming de operador móvil o salida de VPN corporativa en otro país | Revocar la sesión, forzar MFA, confirmar con el usuario fuera de banda |
| Consentimiento OAuth ilícito | El usuario aprueba una app de terceros con scopes amplios (`Mail.Read`, `Mail.Send`, `offline_access`) fuera del catálogo aprobado | App legítima recién adoptada y aprobada por TI | Revocar el consentimiento/token de la app, auditar qué leyó o envió mientras tuvo acceso |
| Delegación de buzón no solicitada | Se agrega un delegado o permiso "enviar como" sobre el buzón sin ticket de soporte asociado | Delegación legítima por asistencia administrativa documentada | Revertir la delegación, revisar quién la configuró y desde dónde |
| Fraude de factura / BEC clásico | Hilo de correo real secuestrado; respuesta con cambio de datos bancarios justo antes de un pago pendiente; dominio look-alike en `Reply-To` | N/A — patrón de alta confianza si coincide con un pago real pendiente | Congelar el pago, verificar por teléfono con el contacto conocido (no el del correo), reportar a banco/legal |
| MFA fatigue / push bombing | Múltiples solicitudes de aprobación push en pocos minutos hasta que el usuario acepta una por error o cansancio | Usuario reintentando su propio login varias veces por mala señal | Revocar la sesión recién aprobada, migrar a MFA resistente a phishing, capacitar al usuario |

## Secuestro de sesión y token

| Señal | Detalle | Falso positivo típico | Contención inmediata |
| --- | --- | --- | --- |
| Reuso de cookie de sesión | Mismo token de sesión usado desde IP/user-agent que cambia sin un nuevo evento de login | Balanceo de carga o proxy corporativo que cambia la IP saliente | Invalidar el token/sesión, forzar nuevo login con MFA |
| Abuso de refresh token | Refresh token usado para emitir access tokens desde ubicaciones o apps nunca vistas para ese usuario | Rotación normal de tokens tras reinicio de la app móvil | Revocar el refresh token, rotar el client secret si aplica |
| Token expuesto en URL/log | Token de acceso visible en logs de servidor o en el header `Referer` tras un flujo OAuth implícito | N/A | Rotar el token inmediatamente, migrar a Authorization Code + PKCE |

## Ransomware / malware

| Señal | Detalle | Falso positivo típico | Contención inmediata |
| --- | --- | --- | --- |
| Renombrado/cifrado masivo de archivos | Un mismo usuario/proceso genera cientos de operaciones PUT/RENAME/DELETE sobre archivos en minutos, con una extensión nueva no reconocida | Migración de datos o backup mal etiquetado como usuario humano | **Aislar el host de la red sin apagarlo** (se pierde memoria forense), preservar evidencia, restaurar desde backup offline |
| Beaconing C2 | Solicitudes salientes periódicas (intervalo casi constante) desde un host hacia el mismo destino externo poco común | Health-check o telemetría legítima de un agente instalado | Bloquear el destino en el firewall, aislar el host, capturar tráfico para análisis |
| Movimiento lateral | Autenticaciones desde una cuenta de servicio hacia múltiples hosts distintos en poco tiempo, fuera de su patrón habitual | Herramienta de gestión de configuración (Ansible/Puppet) ejecutando en lote de forma legítima | Deshabilitar la cuenta, rotar los secretos que usó, revisar qué tocó en cada host |
| Deshabilitación de logging | Un evento de administración apaga o reduce el nivel de auditoría justo antes de actividad sospechosa | Cambio de configuración legítimo y documentado en un cambio programado | Re-habilitar el logging, tratar el sistema como potencialmente comprometido, escalar a forense |

## Amenaza interna y exfiltración

| Señal | Detalle | Falso positivo típico | Contención inmediata |
| --- | --- | --- | --- |
| Descarga masiva fuera de horario | Usuario descarga un volumen muy superior a su promedio, fuera de horario laboral, cerca de una renuncia conocida | Proceso de backup/ETL mal etiquetado como usuario humano | Suspender el acceso temporalmente, coordinar con RRHH/Legal antes de confrontar, preservar logs |
| Acceso fuera de su rol | Usuario accede repetidamente a recursos que no corresponden a su función ni a un ticket abierto | Cambio de rol reciente aún no reflejado en permisos | Revisar permisos (menor privilegio), confirmar con su gerente |
| Subida a almacenamiento personal | Tráfico saliente hacia servicios de almacenamiento personal con volumen alto desde un endpoint corporativo | Uso legítimo de una herramienta aprobada mal clasificada por el proxy | Bloquear el destino si no está en la lista aprobada, revisar con el usuario |

## Compromiso de cuenta o cuenta cloud / IAM

| Señal | Detalle | Falso positivo típico | Contención inmediata |
| --- | --- | --- | --- |
| Credencial IAM nueva inesperada | Se crea una API key/access key para una identidad que normalmente no las gestiona, fuera de un cambio programado | Rotación de credenciales programada por el equipo de plataforma | Revocar la credencial nueva, auditar qué se hizo con ella |
| Escalación vía rol asumido | Una identidad asume un rol con más permisos de los que su política le permitiría directamente, sin ticket de cambio | Automatización legítima de CI/CD asumiendo roles por diseño | Revisar la política de confianza del rol, revocar sesiones activas de ese rol |
| Metadata cloud consultada desde la app | Ver SSRF en la tabla de "Superficie web / API" | — | — |

## Regla de uso

Ninguna causa raíz se afirma solo porque el log "coincide" con una fila de esta
tabla. Cada conclusión debe citar el dato exacto (línea de log, timestamp, ID
de alerta) y, cuando el patrón sea ambiguo entre incidente real y falso
positivo, señalar explícitamente qué dato adicional confirmaría uno u otro
antes de cerrar el diagnóstico — igual que exige `duplicate_avoidance.md` y el
resto de `pentest-brain` para no reportar sin verificar.

La columna "Contención inmediata" es siempre una **propuesta**, nunca una
acción ya ejecutada: el agente no tiene herramientas ni acceso a sistemas
reales en este vertical slice. Sobre incidentes con dinero, cuentas cloud o
datos de terceros de por medio, la propuesta debe incluir a quién escalar
(banco, legal, plataforma cloud) además del paso técnico.
