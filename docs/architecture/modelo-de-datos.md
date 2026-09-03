# Modelo de datos

> Actualizado: 03-09-2026

Entidades, relaciones y reglas de integridad del almacén Supabase. La decisión de
usarlo está en el [ADR-0005](decisions/0005-supabase-como-almacen.md); las acciones
que escriben aquí, en [`contratos-agentes.md`](contratos-agentes.md).

Todos los datos de negocio son **ficticios**. Las credenciales de ejemplo usan
formatos obviamente falsos (`AKIA_EJEMPLO_1234`) para no parecer una fuga real ni
disparar escáneres de secretos.

## Dos grupos de tablas

**Negocio** — el estado de la empresa ficticia sobre el que actúa una acción
aprobada. Es lo que hace que un CRUD aprobado tenga un efecto visible.

**Operación** — el rastro de lo que hicieron los agentes. Es lo que permite que una
aprobación sobreviva entre el momento en que se propone y el momento en que alguien
la decide.

```
corridas ──┬─▶ incidentes ──▶ hallazgos ──▶ aprobaciones ──▶ bitacora_acciones
           │                                                        │
           ├─▶ trazas (una fila por fase, con su origen)            │
           │                                                        │
           └────────────────────────────────────────────────────────┘
                                                                    │
                        actúa sobre ────────────────────────────────┘
                                │
      cuentas · sesiones · ips_bloqueadas · credenciales_api
      hosts · alertas · deploys · transacciones_bd
```

## Tablas de negocio

| Tabla | Identificador | Campos relevantes | Qué acción la toca |
| --- | --- | --- | --- |
| `cuentas` | `CTA-nnn` | `email`, `estado`, `reset_requerido`, `actualizada_en` | `deshabilitar_cuenta`, `forzar_reset_credencial` |
| `sesiones` | `SES-nnn` | `cuenta_id`, `ip`, `user_agent`, `estado`, `creada_en` | `revocar_sesion` |
| `ips_bloqueadas` | `ip` (clave) | `motivo`, `expira_en`, `origen_corrida` | `bloquear_ip` |
| `credenciales_api` | `CRED-nnn` | `cuenta_id`, `etiqueta`, `estado`, `creada_en` | `revocar_credencial_api` |
| `hosts` | `HOST-nnn` | `nombre`, `estado_red`, `aislado_en` | `aislar_host` |
| `alertas` | `ALRT-nnn` | `metrica`, `umbral`, `estado`, `disparada_en` | `cerrar_alerta_falsa` |
| `deploys` | `DEP-nnn` | `servicio`, `version`, `estado`, `desplegado_en` | `revertir_deploy` |
| `transacciones_bd` | `TRX-nnn` | `tabla_afectada`, `estado`, `bloqueando_desde` | `liberar_bloqueo_tabla` |

Ninguna acción del catálogo **crea** filas de negocio: todas modifican filas
existentes, salvo `bloquear_ip`, que inserta en una lista de bloqueo. Un
identificador que pasa su patrón pero no existe produce un error de la acción, no
una entidad nueva. Así, un identificador alucinado por el modelo falla en vez de
inventar una sesión.

## Tablas de operación

### `corridas`

Una fila por ejecución del flujo.

| Columna | Tipo | Nota |
| --- | --- | --- |
| `id` | `uuid` | Clave primaria, generada por la base de datos |
| `canal` | `text` | `dev-chat` · `email-soporte` · `monitoreo` |
| `modo_inferencia` | `text` | `mock` · `live` — **solo describe la inferencia** |
| `modelos` | `jsonb` | Modelo usado en cada fase: triage, especialista, consolidación |
| `llamadas` | `int` | Total de llamadas al modelo, para contrastar contra el presupuesto |
| `usage` | `jsonb` | Tokens de entrada y salida cuando el proveedor los reporta |
| `estado` | `text` | `completada` · `parcial` · `fallida` |
| `diferidos` | `jsonb` | Incidentes que el presupuesto dejó fuera, con su motivo |
| `duracion_ms` | `int` | Tiempo total de la corrida, suma de `trazas.ms` |
| `creada_en` | `timestamptz` | `now()` |

`estado = 'parcial'` es un valor de primera clase, no un caso de error: una corrida
con incidentes diferidos o tareas fallidas **no es una corrida completa** y no debe
poder presentarse como tal.

### `incidentes`

Los incidentes del Entregable de Triage, ya validados.

`id` (`INC-nn`, único por corrida) · `corrida_id` · `titulo` · `tipo` (los 8
valores cerrados) · `canal` · `severidad` · `ataque_activo` · `evidencia` (`jsonb`)
· `especialistas` (`jsonb`) · `motivo_ruteo` · `desviacion_ruteo` (booleano).

`desviacion_ruteo` marca los casos en que el Orquestador propuso un especialista
que la tabla de ruteo no contempla para ese tipo. Se guarda para que la desviación
sea auditable después de la demo, no solo visible durante ella.

**`descartados` y `diferidos` no son lo mismo y viven en columnas distintas de
`corridas`.** `descartados` son señales que el triage evaluó y concluyó que no eran
incidentes —falsos positivos, con el dato que lo demuestra—; no cuelgan de ningún
incidente porque se decidió que no lo eran. `diferidos` son incidentes reales que
el presupuesto dejó sin analizar. Confundirlos sería el peor error de este modelo:
uno dice "lo miré y no era", el otro dice "no lo miré".

### `hallazgos`

Un hallazgo por tarea despachada.

`id` (`uuid`) · `corrida_id` · `incidente_id` · `especialista` · `estado`
(`completado` · `fallido`) · `causa_raiz` · `confianza` · `evidencia` (`jsonb`) ·
`descartado` (`jsonb`) · `viabilidad` · `error` (texto, solo si `estado = 'fallido'`).

### `trazas`

Una fila por fase medida de la corrida, para atribuir la latencia. Decisión y
razonamiento completos en
[ADR-0007](decisions/0007-traza-de-corrida-por-fase.md).

| Columna | Tipo | Nota |
| --- | --- | --- |
| `id` | `uuid` | |
| `corrida_id` | `uuid` | |
| `fase` | `text` | `ingesta` · `triage` · `despacho` · `especialista` · `consolidacion` · `compuerta` · `persistencia` |
| `origen` | `text` | `inferencia` · `almacen` · `local` — a qué se le cobra el tiempo |
| `detalle` | `text` | `incidente_id` y especialista cuando aplica; ruta PostgREST cuando `origen = 'almacen'` |
| `ms` | `int` | Duración medida |
| `estado` | `text` | `ok` · `fallida` |
| `iniciada_en` | `timestamptz` | |

`detalle` nunca guarda cuerpos de prompt ni credenciales, solo identificadores
y rutas — la misma disciplina que el resto del almacén. Las filas se acumulan
en memoria durante la corrida y se insertan en una sola escritura al final: un
insert por fase mediría la latencia de Supabase escribiendo en Supabase.

### `aprobaciones`

La compuerta. Una fila por acción propuesta que requiere autorización.

| Columna | Tipo | Nota |
| --- | --- | --- |
| `id` | `uuid` | No adivinable; es parte de la URL de decisión |
| `hallazgo_id` | `uuid` | De dónde salió |
| `action_id` | `text` | Debe existir en el catálogo del servidor |
| `params` | `jsonb` | Ya validados contra el catálogo antes de insertar |
| `riesgo` | `text` | Copiado **del catálogo**, nunca del modelo |
| `estado` | `text` | `pendiente` · `aprobada` · `rechazada` |
| `justificacion`, `verificacion` | `text` | Lo que dijo el especialista |
| `actor` | `text` | Quién decidió; nulo mientras está pendiente |
| `nota` | `text` | Motivo de la decisión |
| `creada_en`, `decidida_en` | `timestamptz` | |

Restricción: `estado <> 'pendiente'` exige `actor` y `decidida_en` no nulos. Una
aprobación decidida sin constancia de quién la decidió no debe poder existir.

### `bitacora_acciones`

Qué se ejecutó realmente. Una fila por ejecución efectiva, incluidas las acciones
de riesgo bajo que no pasan por la compuerta.

`id` · `corrida_id` · `aprobacion_id` (nulo para las de riesgo bajo) · `action_id`
· `params` · `filas_afectadas` · `antes` (`jsonb`) · `despues` (`jsonb`) ·
`ejecutada_en`.

`antes` y `despues` son lo que hace demostrable el efecto: sin ellos, "se ejecutó"
es una afirmación sin evidencia, que es justo lo que este proyecto no acepta en
ningún otro sitio.

## Seguridad

**RLS activado y deny-by-default en todas las tablas**, sin políticas para `anon`
ni `authenticated`. El único acceso legítimo es la clave `service_role` desde el
servidor Python. Las URLs de proyecto de Supabase son adivinables; la clave anónima
no debe abrir nada si alguien da con la URL.

**La `service_role` no sale del proceso servidor.** Salta RLS por diseño: no se
registra en logs, no se versiona y no llega al navegador. El navegador nunca habla
con Supabase — habla con nuestro servidor, que es el único que tiene credenciales.

**Variables de entorno:** `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY`. Requieren
ampliar la lista blanca `ALLOWED_KEYS` de `dotenv.py`, hoy limitada a `MAAS_*`; ver
[ADR-0005](decisions/0005-supabase-como-almacen.md).

### Decisión de una aprobación

La transición de estado se hace con un procedimiento en la base de datos, no con un
`PATCH` directo:

```sql
create or replace function decidir_aprobacion(
  p_id uuid, p_decision text, p_actor text, p_nota text
) returns aprobaciones
language sql security definer as $$
  update aprobaciones
     set estado = p_decision, actor = p_actor, nota = p_nota, decidida_en = now()
   where id = p_id
     and estado = 'pendiente'
     and p_decision in ('aprobada', 'rechazada')
  returning *;
$$;
```

Si devuelve cero filas, la aprobación ya estaba decidida: el servidor responde
`409` y **no re-ejecuta la acción**. La idempotencia la garantiza el
`where estado = 'pendiente'`, no una comprobación previa en Python — con
`ThreadingHTTPServer` atendiendo en varios hilos, dos pestañas abiertas sobre la
misma aprobación correrían una carrera.

La acción solo se ejecuta si el procedimiento devolvió una fila con
`estado = 'aprobada'`. Ejecutar primero y registrar después dejaría acciones
aplicadas sin constancia.

### Riesgo aceptado

El servidor **no autentica usuarios finales**: sigue fuera de alcance y la demo
asume un único operador en `127.0.0.1`. Consecuencia: cualquiera con acceso a esa
máquina puede aprobar. Se acepta para la demostración y se registra aquí de forma
explícita, siguiendo la plantilla de riesgo aceptado de `SECURITY.md`.

Mitigación parcial que sí se aplica: los `POST` de decisión verifican `Origin` y
`Sec-Fetch-Site`, porque una página maliciosa abierta en el mismo navegador puede
hacer una petición cross-site contra `127.0.0.1`. El `id` de la aprobación es un
`uuid` no adivinable, de modo que no basta con acertar la ruta.

## Sin credenciales de Supabase

La cola de aprobación se muestra **deshabilitada y se dice por qué**. Nunca se
finge que algo se guardó. La interfaz lleva dos indicadores independientes:

- `Inferencia: MOCK | LIVE` — el proveedor de modelo
- `Datos: SUPABASE | NO CONFIGURADO` — el almacén

Son dos ejes distintos. `mock` significa "sin consumo de inferencia", no "sin
efectos externos": una acción aprobada escribe en Supabase en ambos modos.
