# 0005 — Supabase como almacén, vía PostgREST

> Estado: Aceptada · Fecha: 03-09-2026

Supera la parte del [0001](0001-vertical-slice-maas.md) que dejaba el proyecto sin
persistencia, y la línea de `alcance.md` que ponía la persistencia fuera de
alcance. La ausencia de dependencias de runtime, que era la razón de fondo de esa
decisión, se conserva.

## Contexto

El vertical slice no persiste nada: cada request es independiente. Eso bastaba
mientras la salida era texto.

La compuerta de aprobación ([0004](0004-acciones-acotadas-y-aprobacion-humana.md))
lo rompe. Una acción propuesta tiene que sobrevivir entre el momento en que el
agente la propone y el momento —minutos u horas después, en otra sesión del
navegador— en que un humano la decide. Y la acción aprobada tiene que actuar sobre
algo: un CRUD que no modifica ninguna fila no demuestra nada.

Restricción heredada del 0001: el proyecto no tiene dependencias de runtime y
arranca desde un clon limpio. Cualquier almacén que exija instalar un paquete pesa
contra esa propiedad.

## Decisión

Se adoptó Supabase como almacén, accedido **exclusivamente desde el servidor
Python** por su API REST (PostgREST) con `urllib.request`, sin SDK. El navegador
nunca habla con Supabase: habla con nuestro servidor, que es el único que tiene
credenciales.

El esquema, las políticas y el procedimiento de decisión están en
[`modelo-de-datos.md`](../modelo-de-datos.md). Lo que se decidió aquí:

**Sin SDK.** PostgREST es HTTP con JSON. El proyecto ya tiene un cliente HTTP
escrito a mano contra el proveedor de inferencia; el almacén usa el mismo
mecanismo. Se preserva el "sin dependencias de runtime" del 0001.

**RLS deny-by-default en todas las tablas**, sin políticas para `anon` ni
`authenticated`. El único acceso legítimo es la clave `service_role` desde el
servidor. Si la URL del proyecto se filtra —y las URLs de Supabase son
adivinables—, la clave anónima no abre nada.

**La `service_role` no sale del proceso servidor.** Salta RLS por diseño: no se
loguea, no se versiona, no llega al navegador. Esto obliga a ampliar la lista
blanca `ALLOWED_KEYS` de `dotenv.py`, hoy limitada a `MAAS_*`, para admitir
`SUPABASE_*`. Se registra aquí como decisión consciente y no como efecto colateral,
porque esa lista blanca existe precisamente para que ninguna variable entre sin que
alguien lo decida.

**La decisión de una aprobación va por un procedimiento en la base de datos, no
por un `PATCH` directo.** La transición se hace con un `update ... where estado =
'pendiente'`: si devuelve cero filas, la aprobación ya estaba decidida y el
servidor responde `409` sin re-ejecutar la acción. La idempotencia queda garantizada
por la base de datos y no por una comprobación previa en Python, que con
`ThreadingHTTPServer` tendría una carrera entre dos pestañas abiertas.

**`mock` y `live` describen solo la inferencia.** Una acción aprobada se ejecuta
contra Supabase en ambos modos. Para no difuminar el invariante más cuidado del
proyecto, la interfaz muestra **dos indicadores independientes**: `Inferencia:
MOCK | LIVE` y `Datos: SUPABASE | NO CONFIGURADO`. Sin credenciales de Supabase, la
cola de aprobación se muestra deshabilitada y se dice por qué; nunca se finge que
algo se guardó. Es la regla de "sin fallback automático" del 0001 aplicada al
almacén.

## Alternativas descartadas

| Alternativa | Por qué se descartó |
| --- | --- |
| SQLite de la biblioteca estándar | Cero dependencias y cero configuración, pero el estado vive dentro del contenedor: se pierde en cada despliegue y no es visible fuera de la demo |
| Archivo JSON con un lock | `ThreadingHTTPServer` atiende en varios hilos; la idempotencia de la aprobación quedaría en manos de un lock escrito a mano, que es exactamente donde aparecen las carreras |
| Solo en memoria | La cola de aprobación desaparece al reiniciar, y el caso de uso es precisamente que una decisión sobreviva al tiempo entre que se propone y se decide |
| SDK oficial de Supabase | Introduce dependencias de runtime y un gestor de paquetes en un proyecto que arranca desde un clon limpio, a cambio de envolver llamadas HTTP que ya sabemos hacer |
| Exponer Supabase directamente al navegador con la clave `anon` y RLS | Traslada la autorización a políticas RLS y obliga a autenticar usuarios finales, que sigue fuera de alcance; y pone una clave en el cliente sin necesidad |
| Postgres administrado sin la capa Supabase | Exigiría un driver (`psycopg`), rompiendo el "sin dependencias" |

## Consecuencias

**A favor:** la cola de aprobación sobrevive a reinicios y despliegues. El efecto de
una acción aprobada es visible como un cambio real de filas, con su antes y su
después. La atomicidad de la decisión la garantiza la base de datos. Y se mantiene
la propiedad de arrancar sin instalar nada.

**En contra:** aparece una dependencia externa de red y una cuenta que administrar,
con dos consecuencias operativas concretas: el proyecto ya no funciona entero sin
conectividad, y el free tier de Supabase pausa proyectos inactivos —lo que hay que
verificar antes de cualquier demostración. Además, `mock` deja de significar "sin
efectos externos" y pasa a significar "sin consumo de inferencia"; el matiz exige
los dos indicadores de la interfaz para no engañar.

**Coste de revertir:** medio. El acceso queda detrás de un módulo propio, así que
cambiar de almacén es reescribir ese módulo; pero el esquema, las políticas y los
documentos escritos alrededor no se recuperan.

## Fuentes volátiles

- Límites y comportamiento del free tier de Supabase (pausa por inactividad): verificar antes de cada demostración.
