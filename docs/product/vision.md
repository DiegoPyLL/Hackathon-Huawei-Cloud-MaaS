# Visión de Incident Response Agent (sobre MaaS Decision Brief)

## Problema

Investigar un incidente a partir de logs ruidosos, con falsos positivos, consume
tiempo humano y es fácil equivocar la causa raíz si no se exige evidencia
explícita para cada conclusión. En una hackathon, esa ambigüedad reduce
confianza y consume tiempo de explicación.

## Usuario

Un responsable de guardia que recibe logs sintéticos de acceso web con ruido y
necesita, en pocos minutos, una causa raíz defendible y una acción correctiva
propuesta — nunca ejecutada sin autorización explícita fuera de esta demo.

## Propuesta de valor

El agente convierte logs con ruido en un diagnóstico que cita evidencia
concreta (línea de log, timestamp, ID de alerta) y deja visible qué hipótesis
descartó y por qué, usando el catálogo de clases de incidente de
[`deteccion-incidentes.md`](deteccion-incidentes.md).

El razonamiento no ocurre dentro de una sola respuesta: un Orquestador clasifica
y reparte los incidentes entre tres especialistas que investigan en paralelo, y
cada paso es observable mientras corre. Cuando la corrección implica tocar la
base de datos, queda esperando aprobación de una persona en vez de ejecutarse.
El flujo completo está en
[`../architecture/flujo-agentes.md`](../architecture/flujo-agentes.md).

## Promesa

> De logs ruidosos a una causa raíz defendible, con la evidencia a la vista.

## Señales de éxito de la fase actual

- Un clon limpio puede iniciar la demo local sin credenciales.
- El mismo contrato funciona con simulación determinista y con Kostra.
- La interfaz nunca confunde ambos modos.
- `evals/cases.json` cubre incidente web claro, falso positivo (credencial
  vencida vs. fuerza bruta), SSRF a metadata cloud, evidencia insuficiente,
  datos truncados, instrucción hostil embebida en el log, secuestro de correo
  (BEC/regla de reenvío), robo de sesión (AiTM), ransomware, una acción
  correctiva con permisos riesgosos que exige autorización humana explícita, y
  un ataque activo en curso donde la contención inmediata debe ser el primer
  paso.
- Un smoke test puede exigir y probar explícitamente el modo `live`.
- Una corrida con varios incidentes los reparte entre especialistas, declara lo
  que el presupuesto dejó diferido y no presenta como completa una corrida que
  no lo fue.
- Ninguna acción correctiva alcanza la base de datos sin una aprobación humana
  registrada, con su actor y su efecto sobre las filas.

La vertical ya tiene el dominio concreto elegido: respuesta a incidentes. Antes
de cerrar la propuesta para el jurado, ajustar prompts, dataset y copy con logs
más representativos del caso final si aparece uno.

Dos límites siguen en pie y uno cayó. Siguen: el contrato `ChatProvider` como
única frontera con el proveedor, y **sin RAG** — Kostra no ofrece recuperación,
así que todo el conocimiento viaja en el prompt. Cayó el límite de un solo
agente sin herramientas: ver
[ADR-0003](../architecture/decisions/0003-orquestacion-multiagente.md).
