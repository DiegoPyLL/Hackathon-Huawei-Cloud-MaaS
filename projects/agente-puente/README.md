# Puente — de los tres canales al flujo multiagente

El bus reparte un incidente a los canales; este puente hace el camino de vuelta:
recoge las tres versiones y dispara una corrida del flujo multiagente
(`src/maas_demo/orchestrator.py`) para que las correlacione en un solo incidente.

```
   monitoreo (bus :8010) ─┐
   dev-chat      (:8000) ─┼─▶ volcado marcado por canal ─▶ POST /api/incidentes/run
   logs/semáforo (:8028) ─┘                                        │
                                                                    ▼
                             triage ─▶ despacho ─▶ especialistas ─▶ consolidación
                                                                    │
                                                                    ▼
                              incidentes · descartados · hallazgos · acciones
                              pendientes de aprobación · reporte en 5 secciones
                                                                    │
                                                                    ▼
                                        contraste automático contra el groundtruth
```

Cada corrida termina comparando lo que el agente detectó contra lo que de verdad
pasó (`GET /api/verdad` del bus): tipos acertados, no detectados e inventados.
El agente nunca ve esos datos.

## Correr

Con el bus, el chat y el semáforo levantados (`projects/bus-incidentes/levantar_todo.py`)
y el agente en marcha:

```powershell
# agente en modo mock, no necesita API key
$env:MAAS_MODE="mock"; .venv\Scripts\python.exe -m src.maas_demo

# en otra terminal
.venv\Scripts\python.exe projects\agente-puente\puente.py
```

| Comando | Qué hace |
| --- | --- |
| `puente.py` | Una corrida completa: recoge, pregunta al agente, imprime el reporte |
| `puente.py --solo-evidencia` | Arma el volcado y lo imprime, sin llamar al agente |
| `puente.py --json` | La corrida entera como JSON |
| `uvicorn puente:app --port 8020` | Como servicio: `POST /api/corrida`, `GET /api/evidencia` |

## Lo que hay que saber

**Un canal caído no mata la corrida.** Se marca como "no disponible" en el
volcado, que es información útil para el agente: no es lo mismo "no hubo señal
en el chat" que "el chat no estaba".

**El volcado se recorta declarando.** El servidor del agente rechaza peticiones
sobre 64 KiB; si la señal no entra, se trunca dejando la marca en el texto —
nunca en silencio.

**El texto entra marcado como dato.** El prefacio dice explícitamente que el
volcado es material a analizar y nunca instrucciones. Importa porque una de las
fuentes es un chat abierto donde cualquiera escribe lo que quiera.

**En `mock` el agente no analiza.** Devuelve una respuesta determinista y válida
contra el esquema, que sirve para probar la plomería sin gastar cuota — pero no
clasifica de verdad. El contraste lo deja en evidencia: en `mock` los tipos
detectados no coinciden con los reales, y eso es lo esperado. El análisis real
necesita `MAAS_MODE=live` y la API key de MaaS.

**El contraste es el que puntúa al agente.** Al final de cada corrida se compara
lo detectado contra `GET /api/verdad` del bus: tipos acertados, no detectados e
inventados. Es la única forma de saber si el agente clasifica bien o solo produce
texto plausible.
