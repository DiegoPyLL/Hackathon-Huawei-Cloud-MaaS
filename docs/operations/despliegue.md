# Despliegue

> Actualizado: 03-09-2026

## Artefacto

La aplicación se entrega como un contenedor HTTP sin estado:

```bash
docker build -t maas-decision-brief .
docker run --rm -p 8080:8080 --env-file .env maas-decision-brief
```

`.dockerignore` excluye `.env`, configuración de agentes, pruebas y documentación.
Las claves —la de Kostra y la `service_role` de Supabase— se inyectan en tiempo
de ejecución; nunca se copian a la imagen.

El contenedor ya no es del todo sin estado: la cola de aprobación vive en
Supabase. Reiniciarlo no pierde aprobaciones pendientes, pero sí exige que las
credenciales del almacén estén presentes.

## Sin runtime público

El servidor no se publica. Es una decisión, no una elección pendiente: el
servidor incluido no autentica usuarios finales, y las rutas de aprobación
(`POST /api/aprobaciones/{id}`) escriben en la base de datos sin autenticar a
quien decide — la demo asume un único operador en `127.0.0.1`. Publicar ese
endpoint sin una capa de autenticación delante entrega la compuerta de
aprobación de acciones de riesgo alto a cualquiera con el enlace. Se evaluó y
descartó publicar el dashboard en Vercel por esta misma razón; el detalle está
en [ADR-0006](../architecture/decisions/0006-ejecucion-programada-y-manual.md).

Con el flujo multiagente esto pesa más que antes: una corrida son hasta ocho
llamadas al modelo, no una.

Docker sigue siendo el artefacto del proyecto, pero **para ejecución local**:
correr la corrida o el servidor sin instalar Python, no un despliegue público.

## Ejecución sin servidor público

En vez de un runtime siempre encendido, la corrida se dispara de dos formas —
ver [ADR-0006](../architecture/decisions/0006-ejecucion-programada-y-manual.md):

- **Programada:** el workflow `corrida-programada.yml` de GitHub Actions
  (`schedule` + `workflow_dispatch`) repasa **todos** los logs de Supabase en
  `live`, persiste las corridas y publica los hallazgos en la pestaña Security
  del repositorio como alertas de code scanning — ver
  [ADR-0009](../architecture/decisions/0009-salida-como-code-scanning.md).
- **Manual:** `python3 scripts/ejecutablesBase/ejecutar-corrida.py`, el mismo
  código, disparado a mano.

### Secrets del workflow programado

Se leen de GitHub Secrets, nunca de `.env`:

| Secret | Para qué |
| --- | --- |
| `MAAS_API_KEY` | Inferencia en Kostra |
| `MAAS_BASE_URL` | Endpoint del proveedor |
| `MAAS_MODEL` | Modelo por defecto de los tres roles |
| `SUPABASE_URL` | Almacén, vía PostgREST |
| `SUPABASE_SERVICE_ROLE_KEY` | Credencial que ignora RLS; solo en el backend |

`MAAS_MODE` va fijo a `live` en el workflow, no como secret.

### Horario

El cron pedido es **19:00 de Chile todo el año**. GitHub solo entiende UTC y
Chile cambia de huso dos veces al año, así que el workflow declara los dos crons
posibles (`43 22` y `43 23` UTC) y un paso-guarda consulta la hora local con
`zoneinfo` para dejar pasar únicamente el que corresponde. Sin esa guarda, media
parte del año la corrida caería a las 18:00.

El minuto es `:43` y no `:00` porque GitHub descarta ejecuciones programadas en
los minutos de más carga.

### La corrida completa en local

El mismo archivo hace en local todo lo que hace el workflow, y además levanta el
panel al terminar:

```bash
python3 scripts/ejecutablesBase/ejecutar-corrida.py   --con-tests --desde-supabase --mode live   --sarif evals/results/incidentes.sarif   --json-out evals/results/corrida.json   --panel
```

Con `--mode mock` la misma línea ejercita la cadena entera sin gastar saldo.

`--presupuesto-minutos` corta la corrida entre volcados al agotarse y declara
cuántos quedaron sin procesar: el workflow usa 330 minutos para cortar antes de
que el runner muera a las 6 horas, porque un corte del runner desaparece sin
dejar dicho qué faltó.

## Gate de evidencia

```bash
python3 scripts/ejecutablesBase/prueba-humo.py --url http://127.0.0.1:8080 --require-mode live
```

Guardar junto a la demo: fecha, commit del proyecto, **proveedor y modelo de
cada rol**, run del workflow programado (si aplica) y salida del smoke test.
No guardar las claves ni cuerpos completos de conversación.

## Comprobaciones antes de cada demostración

Dos dependencias externas pueden dejar la demo muerta sin previo aviso:

1. **Saldo de Kostra.** Es prepago y **compartido con la cuenta del chat web**:
   alguien usando el chat consume el mismo saldo. Un `402` a mitad de una corrida
   aborta la corrida entera. Verificar saldo antes de presentar.
2. **Proyecto de Supabase activo.** El free tier pausa proyectos inactivos. Un
   proyecto pausado deja la cola de aprobación sin almacén; la interfaz lo dirá
   con todas sus letras, pero no habrá compuerta que demostrar.

## Rollback y contingencia

- Rollback: volver al commit anterior y correr desde ahí, local o vía
  `workflow_dispatch`. El esquema de Supabase sí evoluciona: una migración que
  quite columnas exige revisar si el código anterior sigue funcionando contra
  el esquema nuevo.
- Corrida programada que falla: el log del workflow queda como evidencia; no
  reintentar en silencio. Investigar y, si hace falta, disparar
  `workflow_dispatch` a mano tras corregir.
- Proveedor caído o sin saldo: mostrar el error tal cual —incluido el código y qué
  significa— y cambiar manualmente a `mock` si se necesita continuar la
  explicación de UX, diciéndolo en voz alta.
- Supabase caído: la cola de aprobación se muestra deshabilitada y se explica por
  qué. No se simula una aprobación guardada.
- Credencial expuesta: revocar y rotar — tanto en `.env` local como en GitHub
  Secrets — antes de volver a correr.
