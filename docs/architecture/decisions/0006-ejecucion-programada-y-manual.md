# 0006 — Ejecución programada en GitHub Actions y script manual

> Estado: Aceptada · Fecha: 03-09-2026

## Contexto

Hasta ahora el proyecto solo se ejecuta a mano: `python3 -m src.maas_demo` para
el agente único, o `evaluar.py` y `prueba-humo.py` para verificarlo. El flujo
multiagente del [ADR-0003](0003-orquestacion-multiagente.md) y la compuerta de
aprobación del [ADR-0004](0004-acciones-acotadas-y-aprobacion-humana.md)
necesitan una corrida que se dispare sola, para que la cola de aprobación
tenga algo con lo que demostrar el efecto entre dos sesiones del navegador —
justo lo que motivó el [ADR-0005](0005-supabase-como-almacen.md).

Se evaluó publicar el dashboard en Vercel con una capa API propia, para que la
corrida y la aprobación vivieran detrás de una URL pública. Se descartó: el
catálogo cerrado de acciones (ADR-0004) tendría que vivir duplicado o
compartido entre dos runtimes HTTP, y una URL pública rompe el supuesto
explícito de [`modelo-de-datos.md`](../modelo-de-datos.md) de que el servidor
no autentica usuarios finales y la demo asume un único operador en
`127.0.0.1`. Publicarla entrega la compuerta de aprobación de acciones de
riesgo alto a cualquiera con el enlace. Se prioriza que el proyecto funcione
sobre tenerlo publicado.

## Decisión

Se ejecuta la corrida de dos formas, con el mismo código y dos disparadores
distintos.

**Dos workflows de GitHub Actions, separados porque tienen fronteras de
confianza distintas:**

- `ci.yml`, en cada push: `python3 -m unittest discover -s tests` y
  `evaluar.py --mode mock`. Sin secretos — un PR desde un fork no debe poder
  tocar la clave de Kostra ni la `service_role` de Supabase.
- `corrida-programada.yml`, con `schedule` y `workflow_dispatch`: ejecuta la
  corrida completa en `live` contra Kostra, escribe en Supabase y sube el
  reporte ejecutivo como artifact. Usa GitHub Secrets, nunca `.env`.

**Ejecución manual** con
`scripts/ejecutablesBase/ejecutar-corrida.py`, junto a los scripts que ya
existen (`evaluar.py`, `prueba-humo.py`). El workflow programado es solo el
disparador: corre el mismo script.

**La corrida automática propone, nunca decide.** Las acciones de riesgo medio
y alto quedan como filas `pendiente`; un humano las aprueba después desde el
dashboard local, en `127.0.0.1`. El ADR-0004 no tiene excepción para una
corrida desatendida.

**En Actions las variables vienen de Secrets, no de `.env`.** La lista blanca
`ALLOWED_KEYS` de `dotenv.py` gobierna el archivo `.env` local; no aplica en
Actions, donde `Config.from_env()` lee `os.environ` directamente, poblado por
GitHub Secrets.

## Alternativas descartadas

| Alternativa | Por qué se descartó |
| --- | --- |
| Publicar el dashboard en Vercel con una capa API propia | Parte el runtime HTTP en dos plataformas; una URL pública rompe el supuesto de operador único de `modelo-de-datos.md` y expone la compuerta de aprobación de riesgo alto |
| Cron en un servidor propio | Añade infraestructura que administrar y un runtime siempre encendido, contra la propiedad de "arranca desde un clon limpio" del ADR-0001 |
| Solo ejecución manual, sin Actions | No demuestra la cola de aprobación sobreviviendo entre sesiones sin que alguien dispare la corrida a mano cada vez |
| Un servicio siempre encendido en vez de un cron | Coste y superficie permanentes que el proyecto no necesita para una corrida periódica |

## Consecuencias

**A favor:** la corrida se demuestra sola, sin depender de que alguien la
dispare antes de la demo. El log de Actions queda como evidencia de que
corrió. El CI protege contra romper el contrato sin gastar saldo ni exponer
secretos a un fork.

**En contra:** una corrida programada consume saldo prepago de Kostra
**compartido con la cuenta del chat web** — el mismo riesgo que
[`despliegue.md`](../../operations/despliegue.md) ya señala como capaz de
matar la demo si alguien lo agota antes de presentar. El cron tiene que ser
poco frecuente; el presupuesto de
[`flujo-agentes.md`](../flujo-agentes.md) (`MAX_LLAMADAS_POR_CORRIDA = 8`) es
el techo real de gasto por ejecución, y un `402` a mitad de corrida la aborta
entera.

**Coste de revertir:** bajo. Los workflows son disparadores; quitar
`corrida-programada.yml` deja intacto el script y la ejecución manual.

## Fuentes volátiles

- Granularidad mínima del cron: *«The shortest interval you can run scheduled
  workflows is once every 5 minutes.»*
- Desactivación por inactividad: *«In a **public** repository, scheduled
  workflows are automatically disabled when no repository activity has
  occurred in 60 days.»* Redactada para repositorios públicos; no se asume
  para uno privado.
- Fiabilidad del disparador: *«The `schedule` event can be delayed during
  periods of high loads… High load times include the start of every hour. If
  the load is sufficiently high enough, some queued jobs may be dropped.»* Por
  eso el cron se programa en un minuto que no sea el `:00`, y la corrida
  programada no se trata como garantizada.
- Retención de artifacts: 90 días por defecto, configurable.
- El free tier de Supabase pausa proyectos inactivos (ver ADR-0005): una
  corrida programada lo mantiene despierto, efecto colateral favorable.

Fuentes: [events-that-trigger-workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) · [download-workflow-artifacts](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts) — consultadas el 03-09-2026, verificar antes de fijar el cron.
