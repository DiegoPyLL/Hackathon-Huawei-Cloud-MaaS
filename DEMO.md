# Despliegue completo, paso a paso

## ¿El agente resuelve solo o hay que usar el panel?

Hay **tres niveles distintos**, y conviene tenerlos claros antes de la demo:

| | Qué hace | ¿Automático? |
| --- | --- | --- |
| **Agente 1** — analista (`:8080`, panel `:8001`) | Lee, clasifica, diagnostica. **Nunca ejecuta nada** | Arranca **apagado**. Una vez prendido, procesa **solo** cada señal que llega |
| **Flujo multiagente** (lo dispara el puente) | Triage → especialistas → propone acción del catálogo | Se dispara **a mano**. Las acciones quedan **pendientes de aprobación humana**, no se ejecutan |
| **Agente 2** — rango de refuerzo (`harden.py`) | **Sí ejecuta**: edita código en el contenedor y lo reinicia | Se lanza a mano y desde ahí actúa solo. Necesita Docker |

**El panel no es obligatorio.** Podés correr todo por línea de comandos con el
puente. Lo que sí es cierto: el agente **no arranca solo** — o lo prendés con el
toggle del panel, o lo disparás con el comando del puente.

Y salvo el rango de refuerzo, **nada se ejecuta automáticamente**: las acciones
correctivas quedan en una cola esperando que un humano las apruebe. Eso es
deliberado, viene del [ADR-0004](docs/architecture/decisions/0004-acciones-acotadas-y-aprobacion-humana.md).

---

## Paso 1 — Preparar el entorno (una sola vez)

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" httpx openai pydantic
```

## Paso 2 — Configurar el `.env` en la raíz

```
MAAS_MODE=live
MAAS_API_KEY=<la key>
MAAS_BASE_URL=https://ai.kostra.cloud/v1
MAAS_MODEL=glm-5.2
MAAS_TIMEOUT_SECONDS=180
```

Dos cosas que cuestan una demo si se ignoran:

- **Solo `glm-5.2` está habilitado.** `deepseek-v4-pro`, `deepseek-v3.2` y
  `qwen3-32b` devuelven **403**. Si el `.env` apunta a otro, todo falla.
- **`MAAS_TIMEOUT_SECONDS` tiene que ser 180.** Con 45 (el default) un triage
  real se corta por timeout: una llamada trivial tarda 6s, pero una con el
  volcado completo pasa el minuto.

## Paso 3 — Levantar los servicios

```powershell
.venv\Scripts\python.exe projects\bus-incidentes\levantar_todo.py
```

Levanta los cinco en orden (los de abajo leen de los de arriba). Para no gastar
cuota: `--mock`.

| Puerto | Servicio | Qué es |
| --- | --- | --- |
| 8010 | bus | Fuente de verdad. Sin UI, solo API |
| 8000 | dev-chat | Chat tipo Slack del equipo |
| 8028 | semáforo | Dashboard de estado + consola de logs |
| 8001 | demo | Los 3 canales alimentando al agente |
| 8080 | Agente 1 | Incident Response Agent |

Verificá que responden:

```bash
curl http://localhost:8080/api/health    # tiene que decir "live" y "glm-5.2"
curl http://localhost:8010/api/verdad
```

## Paso 4 — Abrir las pantallas, en este orden

1. **http://localhost:8028** — el semáforo. Empezá acá: es el "así se ve un
   sistema sano" (o ya con algo en rojo si hay incidentes vivos).
2. **http://localhost:8000** — el dev chat corriendo solo. Mostrá que un
   incidente **no se distingue visualmente** de la charla: esa es la gracia.
3. **http://localhost:8001** — la demo del agente, con los 3 canales entrando.
4. **http://localhost:8080** — el Agente 1.

## Paso 5 — Provocar un incidente

```bash
curl -X POST http://localhost:8010/api/incidentes/provocar \
  -H "Content-Type: application/json" \
  -d '{"escenario":"caida_tras_deploy"}'
```

Y mirá **las tres pantallas a la vez**:

- **8028** → el panel del servicio se pone rojo y caen las líneas de alerta al log
- **8000** → alguien lo comenta en `#incidentes`, entre la charla normal
- **8010** → `reportado_en` muestra por qué canales entró

Una sola causa, tres síntomas distintos. Y a propósito **no todos los canales
reportan todo** (el chat comenta ~80%): si los tres dijeran siempre lo mismo,
correlacionar sería trivial.

Escenarios recomendados:

| Escenario | Para mostrar |
| --- | --- |
| `caida_tras_deploy` | El clásico, se entiende solo |
| `credential_stuffing_horizontal` | Seguridad, ataque activo, acción de bloqueo |
| `disco_motor_datos` | Capacidad, rutea a **dos** especialistas |

Los 16: `curl http://localhost:8010/api/escenarios`

## Paso 6 — Que el agente resuelva

**Opción A — por panel (visual):** en http://localhost:8001, prender el toggle
del agente. Desde ahí procesa solo cada señal que llega.

**Opción B — por comando (completo):**

```powershell
.venv\Scripts\python.exe projects\agente-puente\puente.py
```

Recoge las tres versiones del incidente y dispara la corrida. Devuelve:

1. **Evidencia recogida** — cuántas líneas dio cada canal, y cuál estaba caído
2. **Triage** — incidentes con tipo, severidad, ruteo y evidencia textual, **más
   lo que descartó y por qué**
3. **Hallazgos** — causa raíz, confianza e hipótesis descartadas por especialista
4. **Acciones esperando aprobación** — del catálogo cerrado, **sin ejecutar**
5. **Reporte ejecutivo** en las 5 secciones del contrato
6. **Contraste contra la verdad** — acertados, no detectados, inventados

El paso 6 es el que vale: separa clasificar bien de producir texto plausible. El
agente nunca ve esos datos.

## Paso 7 (opcional) — El rango de refuerzo, donde el agente sí ejecuta

**Requiere Docker Desktop corriendo.**

```bash
cd reinforcement-range
./reset.sh                     # levanta el objetivo vulnerable
./run-harden.sh                # el agente que edita y reinicia de verdad
python watch-and-defend.py     # le pasa los logs en vivo al Agente 1
```

Es el contraste del pitch: el Agente 1 diagnostica sin tocar nada; el Agente 2
sí interviene sobre un objetivo real.

---

## Antes de pararte adelante

**Una corrida `live` tarda ~2,5 minutos** (3 llamadas encadenadas contra Hong
Kong). Opciones, en orden:

1. Disparar la corrida **antes** de empezar a hablar y volver a ella
2. Mostrar el flujo en `--mock` (instantáneo) y enseñar una corrida `live` ya
   hecha como evidencia
3. Video de respaldo

**No afirmar model routing.** Solo hay un modelo habilitado, así que "modelo
barato para clasificar, fuerte para consolidar" **no se puede demostrar**.

**Si un servicio se cae, el resto sigue.** El semáforo sin bus queda en verde, el
chat sigue con charla local, el puente declara el canal "no disponible". Ninguna
pantalla se rompe por culpa de otra.
