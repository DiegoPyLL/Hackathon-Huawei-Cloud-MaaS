# 0002 — Rango de refuerzo con ejecución real (tool-calling)

> Estado: Aceptada · Fecha: 03-09-2026

## Contexto

El Incident Response Agent (ver `0001-vertical-slice-maas.md`) es deliberadamente
de solo lectura: investiga logs y propone una corrección en texto, pero nunca
ejecuta nada (`docs/product/alcance.md`, `AGENTS.md`). Ese invariante se
mantiene sin cambios para ese agente.

Para la demo del hackathon se necesita, además, un ejercicio distinto: probar
si `deepseek-v4-pro` (vía Kostra) puede reforzar la seguridad de un entorno de
verdad — con ejecución real de comandos, no solo texto — y que el equipo pueda
después atacarlo a ciegas para validar si la defensa aguanta. Se confirmó con
una llamada real a `https://ai.kostra.cloud/v1/chat/completions` que el modelo
soporta tool-calling nativo (formato `tools`/`tool_calls` estándar), lo que
permite un loop de agente real sin parseo de texto.

Se midió también la latencia real del modelo: 6-113 segundos por turno según
el tamaño del prompt/respuesta. Con un tool-calling loop, cada comando
ejecutado implica un turno completo, así que el presupuesto de acciones debe
acotarse pensando en minutos reales, no en "iteraciones baratas".

Dar a un LLM shell real sin filtro implica que la contención del entorno deja
de ser buena práctica y pasa a ser el único mecanismo de seguridad: no hay
ningún filtro de comandos del lado del prompt.

## Decisión

Se construye un **rango de pruebas aislado**, separado del Incident Response
Agent, con dos piezas:

**Contenedor objetivo** — una app vulnerable con bugs y cadenas de ataque
reales (deliberadamente no enumerados en este documento ni en ningún otro
spec, para preservar la integridad del ataque a ciegas del equipo). Corre en
una red Docker `internal` con subred fija (sin salida a internet — verificado
empíricamente: una petición saliente devuelve `Network unreachable`),
`--cap-drop=ALL`, sin `--privileged`, con límites de CPU/memoria/procesos, y
sin ningún volumen del host real montado — todo lo que el modelo escriba vive
y muere dentro del contenedor. Al arrancar carga los datos de `seed/` (ver
abajo).

El equipo ataca el contenedor por su **IP fija dentro de esa red** (asignada
con `--ip` sobre la subred de la red `internal`), **no por un puerto
publicado con `-p`** — se verificó empíricamente que Docker no publica
puertos en redes `internal` (el intento de publicar falló; sin embargo el
host sí llega directo a la IP del contenedor dentro de esa red, porque está
conectado a ese bridge). Usar una IP fija evita que cambie entre rondas.

**Orquestador** — script Python en el host que llama a Kostra con un
`SYSTEM_PROMPT` nuevo de "hardening agent" (distinto y no mezclado con el del
Incident Response Agent), expone un único tool `run_shell(comando)` ejecutado
vía `docker exec` contra el contenedor objetivo, y corre el loop hasta el
primero de estos topes: **12 comandos**, **30 segundos por comando**, **15
minutos totales**. Cada comando y su output quedan en un transcript que no se
muestra al equipo hasta después de la fase de ataque.

**`seed/`** — directorio versionado en el repo (JSON/SQL simple) con cuentas
falsas y registros de prueba. Cualquier persona del equipo suma más datos
editando o agregando archivos ahí; se carga en cada reset del contenedor. No
es un servicio en vivo.

**Ciclo de vida**: `docker run` desde imagen fija + `seed/` → ronda de
refuerzo (orquestador + modelo) → el equipo ataca el puerto publicado con sus
herramientas habituales → `docker rm -f` + `docker run` de nuevo → repetir
tantas rondas como se quiera, en la misma sesión o en sesiones futuras.

**Reporte**: al cerrar una ronda, se compara el transcript de lo que hizo el
modelo contra lo que encontró el equipo atacando, más un diff del estado
final contra la imagen base — insumo para la demo, no se genera ni se
muestra durante la ronda.

## Alternativas descartadas

| Alternativa | Por qué se descartó |
| --- | --- |
| El modelo solo propone un diff/plan y un script lo aplica (sin ejecución propia) | No cumplía el pedido explícito de ejecución real; hacía el ataque menos representativo de un incident responder de verdad |
| Set curado de acciones (`rotar_credencial`, `bloquear_ip`, etc.) en vez de shell libre | Más seguro y auditable, pero menos realista; se descartó a favor de shell real dado el objetivo explícito de máximo realismo |
| Solo archivos de config + SQLite, sin app corriendo | No da superficie de ataque real (curl/ffuf/sqlmap no tienen nada que explotar); reduce el ejercicio a diffear JSON |
| Stack multi-servicio con red simulada completa | Alcance de varios días, no cabe en el tiempo restante de hackathon |
| Loop de agente basado en parseo de texto (`EXEC: comando`) | Innecesario: se confirmó tool-calling nativo real en Kostra/deepseek-v4-pro |
| `--network none` en el contenedor objetivo | Sin interfaz de red en absoluto, ni siquiera para que el host la ataque; se usa red `internal` en su lugar |
| Publicar el puerto con `-p` sobre la red `internal` | Verificado empíricamente que no funciona: Docker no publica puertos en redes `internal`. Se ataca por IP fija dentro de la red en su lugar (el host sí llega directo al bridge) |

## Consecuencias

**A favor:** ejercicio de red-team genuino sobre un agente con ejecución
real, reutilizable indefinidamente (reset rápido), con evidencia (transcript)
para el reporte del hackathon; no toca ni pone en riesgo el invariante de
solo-lectura del Incident Response Agent, que queda intacto.

**En contra:** shell sin filtro exige que la contención del contenedor sea
perfecta — un fallo de aislamiento (red, capacidades, límites) es la única
red de seguridad restante. Cada ronda completa puede tardar varios minutos
por la latencia real del modelo (hasta ~15 min en el peor caso).

**Coste de revertir:** bajo. Es un subsistema nuevo y separado (contenedor +
script orquestador); eliminarlo no afecta al Incident Response Agent ni a su
`SYSTEM_PROMPT`.

## Confidencialidad

El inventario real de vulnerabilidades y cadenas de ataque de la app objetivo
vive únicamente en el código/config de esa app, nunca en este documento ni en
ningún otro spec — es deliberado, para que el ataque del equipo sea a ciegas
de verdad.
