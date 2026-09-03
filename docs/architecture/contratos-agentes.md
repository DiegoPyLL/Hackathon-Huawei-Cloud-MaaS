# Contratos entre agentes

> Actualizado: 03-09-2026

Qué se pasan los cuatro roles del [flujo](flujo-agentes.md) y cómo se valida.
Regla general: **el modelo propone, el servidor valida**. Ningún campo que decida
permisos, riesgo o presupuesto se acepta tal como viene del modelo.

## A — Entregable de Triage

Salida del Orquestador en la fase 1.

```json
{
  "version": "1",
  "incidentes": [
    {
      "id": "INC-01",
      "titulo": "Ráfaga de 401 contra varias cuentas desde una sola IP",
      "tipo": "acceso-identidad",
      "canal": "monitoreo",
      "severidad": "alta",
      "ataque_activo": true,
      "evidencia": [
        "10:14:22 401 POST /login user=ana.soto ip=203.0.113.47 alert=ALRT-9014"
      ],
      "especialistas": ["secops"],
      "motivo_ruteo": "Patrón horizontal: la misma IP contra usuarios distintos."
    }
  ],
  "descartados": [
    {
      "senal": "Tres 401 de la cuenta svc-cache",
      "motivo": "Falso positivo: una sola identidad objetivo, patrón de credencial vencida y no de fuerza bruta",
      "evidencia": "10:02:11 401 POST /login user=svc-cache ip=10.0.4.9"
    }
  ]
}
```

| Campo | Tipo | Regla |
| --- | --- | --- |
| `version` | `"1"` | Literal. Un valor distinto invalida el entregable |
| `incidentes[].id` | string | `^INC-\d{2}$`, único dentro del entregable |
| `incidentes[].titulo` | string | 1..120 caracteres |
| `incidentes[].tipo` | enum | Exactamente uno de los 8 canónicos |
| `incidentes[].canal` | enum | `dev-chat` · `email-soporte` · `monitoreo` |
| `incidentes[].severidad` | enum | `baja` · `media` · `alta` · `critica` |
| `incidentes[].ataque_activo` | booleano | Obligatorio; determina prioridad al recortar |
| `incidentes[].evidencia` | lista de string | 1..5 elementos, cada uno 1..300 caracteres |
| `incidentes[].especialistas` | lista de enum | 1..2 elementos de `dba` · `sysadmin` · `secops` |
| `incidentes[].motivo_ruteo` | string | 1..240 caracteres |
| `descartados` | lista | **Obligatoria**, puede ir vacía |
| `descartados[].senal` / `.motivo` / `.evidencia` | string | Los tres obligatorios |

Los 8 tipos canónicos como valores literales, en kebab-case y sin acentos igual que
el resto de identificadores del repositorio:

| # | Tipo (documentación) | Valor en el contrato |
| --- | --- | --- |
| 1 | Indisponibilidad | `indisponibilidad` |
| 2 | Degradación | `degradacion` |
| 3 | Error funcional | `error-funcional` |
| 4 | Acceso e identidad | `acceso-identidad` |
| 5 | Datos | `datos` |
| 6 | Integración y terceros | `integracion-terceros` |
| 7 | Capacidad | `capacidad` |
| 8 | Seguridad | `seguridad` |

La lista es cerrada: un valor fuera de ella invalida el entregable. El clasificador
nunca inventa una categoría nueva ni responde "otro" sin que quede explícito por
qué, tal como exige
[`../product/clasificacion-incidentes.md`](../product/clasificacion-incidentes.md).

**Por qué `descartados` es obligatorio.** El diferenciador declarado del proyecto
es que se vea qué se descartó y por qué. Si es opcional, el modelo lo omitirá en
cuanto tenga prisa. Una lista vacía es una afirmación —"no descarté nada"— y se
puede evaluar; un campo ausente no.

## B — Hallazgo del especialista

Salida de DBA, SysAdmin o SecOps en la fase 3.

```json
{
  "version": "1",
  "incidente_id": "INC-01",
  "especialista": "secops",
  "causa_raiz": "Credential stuffing horizontal desde 203.0.113.47.",
  "confianza": "alta",
  "evidencia": [
    "10:14:22 401 POST /login user=ana.soto ip=203.0.113.47 alert=ALRT-9014",
    "10:14:23 401 POST /login user=j.paredes ip=203.0.113.47"
  ],
  "descartado": [
    {
      "hipotesis": "Credencial vencida de una cuenta de servicio",
      "dato_que_la_descarta": "Los 401 apuntan a 14 usuarios distintos, no a uno"
    }
  ],
  "viabilidad": "accionable",
  "accion": {
    "action_id": "bloquear_ip",
    "params": { "ip": "203.0.113.47", "motivo": "Credential stuffing", "ttl_horas": 24 },
    "justificacion": "Corta el ataque en curso sin tocar cuentas de personas reales.",
    "verificacion": "No deben aparecer nuevos 401 desde esa IP en los siguientes 10 minutos."
  }
}
```

| Campo | Tipo | Regla |
| --- | --- | --- |
| `incidente_id` | string | Debe existir en el Entregable de Triage de esta corrida |
| `especialista` | enum | Debe coincidir con el de la tarea despachada |
| `causa_raiz` | string | 1..600 caracteres |
| `confianza` | enum | `alta` · `media` · `baja` · `insuficiente` |
| `evidencia` | lista de string | 1..8 elementos |
| `descartado` | lista | **Obligatoria**, puede ir vacía; cada par con sus dos campos |
| `viabilidad` | enum | `accionable` · `requiere_mas_datos` · `no_accionable` |
| `accion` | objeto o `null` | Ver reglas cruzadas |

### Reglas cruzadas, validadas en servidor

1. `confianza: "insuficiente"` ⟹ `accion` debe ser `null`.
2. `viabilidad != "accionable"` ⟹ `accion` debe ser `null`.
3. `accion.action_id` debe existir en el catálogo. Si no, el hallazgo se rechaza.
4. `accion.params` debe traer exactamente los parámetros que el catálogo declara
   para ese `action_id`, y cada uno debe pasar su validador.

No se confía en que el modelo se autocontenga: las cuatro reglas se comprueban
después de recibir la respuesta.

### Lo que el modelo no declara

`riesgo` y `requiere_aprobacion` **no aparecen en el contrato**. Salen del catálogo
del servidor indexados por `action_id`. Permitir que el modelo etiquete su propia
acción como de bajo riesgo sería devolver la decisión de autorización al componente
que no es de confianza.

## C — Reporte Ejecutivo

Salida del Orquestador en la fase 4. Es **texto**, no JSON, en las cinco secciones
que el proyecto ya usa y que `evaluar.py` ya sabe verificar:

```
Tipo de incidente
Causa raíz probable
Evidencia
Qué se descartó
Acción correctiva
```

Se transmite como eventos `delta`. Al cerrar, el evento `done` lleva los metadatos
de la corrida: incidentes analizados, diferidos, fallidos, aprobaciones creadas,
llamadas al modelo por rol, modelo usado en cada fase, latencia y modo.

El reporte debe **nombrar explícitamente** lo diferido y lo fallido. Un reporte que
no menciona los dos incidentes que el presupuesto dejó fuera es un reporte
incompleto presentado como completo.

## Extracción y validación de JSON

Los contratos A y B viajan como texto generado por un modelo. El procedimiento:

1. **Extraer.** Se acepta el objeto JSON directo, envuelto en vallas de código, o
   rodeado de prosa: se toma el primer objeto balanceado desde la primera `{`.
2. **Validar** contra el esquema y los enums cerrados. Estrictamente: un `tipo`
   fuera de los 8 es un error, no un valor que se normaliza.
3. **Reintentar una vez**, devolviendo al modelo el error concreto ("`tipo` debe
   ser uno de: …; recibido: `otro`").
4. **Fallar declarando.** Si el segundo intento tampoco valida, la tarea queda
   `fallida` con el contrato que se rompió, o la corrida entera termina en `error`
   si lo que falló fue el triage.

**Nunca se fabrica un entregable de reemplazo.** Es la misma regla del "sin
fallback automático de `live` a `mock`" del ADR-0001, aplicada a los contratos: un
resultado inventado es peor que un fallo declarado.

## Catálogo cerrado de acciones

El modelo **nunca emite SQL**. Elige un `action_id` de esta lista y rellena
parámetros tipados; el servidor lo mapea a una operación predefinida y
parametrizada. Ver [ADR-0004](decisions/0004-acciones-acotadas-y-aprobacion-humana.md).

| `action_id` | Qué hace | Parámetros | Riesgo | Aprobación |
| --- | --- | --- | --- | --- |
| `cerrar_alerta_falsa` | Marca una alerta como falso positivo | `alerta_id` | bajo | no |
| `anotar_incidente` | Añade una nota al historial del incidente | `incidente_id`, `nota` | bajo | no |
| `bloquear_ip` | Añade una IP a la lista de bloqueo | `ip`, `motivo`, `ttl_horas` | medio | **sí** |
| `revocar_sesion` | Marca una sesión como revocada | `sesion_id` | medio | **sí** |
| `forzar_reset_credencial` | Marca la cuenta para reset obligatorio | `cuenta_id` | alto | **sí** |
| `deshabilitar_cuenta` | Desactiva una cuenta | `cuenta_id`, `motivo` | alto | **sí** |
| `revocar_credencial_api` | Revoca una API key | `credencial_id` | alto | **sí** |
| `aislar_host` | Marca el host aislado de red, **sin apagarlo** | `host_id` | alto | **sí** |
| `liberar_bloqueo_tabla` | Cancela una transacción bloqueante | `transaccion_id` | alto | **sí** |
| `revertir_deploy` | Marca un deploy para rollback | `deploy_id` | alto | **sí** |

`aislar_host` nunca apaga la máquina: apagarla destruye la memoria y con ella la
evidencia forense. La regla viene de
[`../product/deteccion-incidentes.md`](../product/deteccion-incidentes.md) y el
catálogo la hace estructural en vez de dejarla como una recomendación del prompt.

Las dos acciones de riesgo bajo no requieren aprobación, pero **sí quedan
registradas** en la bitácora junto a la corrida que las originó.

### Validadores de parámetros

| Parámetro | Validación |
| --- | --- |
| `ip` | `ipaddress.ip_address()`; se rechazan loopback, enlace local y multicast |
| `alerta_id` | `^ALRT-\d{1,6}$` |
| `sesion_id` | `^SES-\d{1,6}$` |
| `cuenta_id` | `^CTA-\d{1,6}$` |
| `credencial_id` | `^CRED-\d{1,6}$` |
| `host_id` | `^HOST-\d{1,6}$` |
| `transaccion_id` | `^TRX-\d{1,6}$` |
| `deploy_id` | `^DEP-\d{1,6}$` |
| `incidente_id` | `^INC-\d{2}$`, y debe existir en la corrida |
| `nota`, `motivo` | 1..280 caracteres, sin caracteres de control |
| `ttl_horas` | Entero, 1..168 |

Un identificador que valida el patrón pero no existe en la base de datos produce un
error de la acción, no una fila nueva: ninguna acción del catálogo crea entidades
de negocio que no existían.

**Por qué patrones estrictos y no solo escapado.** El escapado protege contra la
inyección; el patrón protege además contra que el modelo invente identificadores
plausibles. Un `sesion_id` alucinado que pasa el escapado sigue siendo una acción
sobre una sesión equivocada.
