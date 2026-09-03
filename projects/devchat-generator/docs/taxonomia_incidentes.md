# Taxonomía canónica de incidentes

## Principio de diseño
Un incidente es un incidente independientemente de por dónde entró.
Si se define un tipo distinto por canal (email vs. monitoring vs. dev chat),
el mismo problema de producción genera tres incidentes que no se pueden
correlacionar. Lo que cambia por canal no es el tipo, es la **estructura de
la señal** y lo que falta en ella (ver `channels/*/NOTES.md`).

## 8 tipos de incidente
1. **Indisponibilidad** — servicio caído, endpoint no responde
2. **Degradación** — latencia, timeouts, lentitud
3. **Error funcional** — bug, cálculo incorrecto, flujo roto
4. **Acceso e identidad** — login, permisos, MFA, cuenta bloqueada
5. **Datos** — faltantes, incorrectos, sincronización fallida
6. **Integración y terceros** — API externa, webhook, pasarela de pago
7. **Capacidad** — disco, memoria, cuota, rate limit
8. **Seguridad** — actividad sospechosa, credencial expuesta, phishing

## 2 buckets que no son incidente (deben existir)
- **Solicitud** — consulta, how-to, feature request, cambio
- **Ruido** — duplicado, alerta ya recuperada, conversación sin incidente

Sin estos dos buckets el agente infla sus propias métricas de "incidentes
detectados". No son un detalle opcional.

## Límite de clases
8 + 2 es el techo práctico. Con más clases y poco tiempo de evaluación, el
clasificador confunde categorías vecinas (ej. degradación vs. error funcional)
y no se nota hasta el pitch.

## Trampa transversal a los tres canales
La severidad se calcula por impacto real, no por el tono del mensaje que la
reporta. Un canal urgente en el texto puede ser severidad baja; un mensaje
tranquilo puede describir un corte total. Si el prompt de clasificación deja
que el modelo infiera severidad del lenguaje, la priorización queda invertida.
