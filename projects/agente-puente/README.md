# Puente — de los tres canales al agente

El bus reparte un incidente a los canales; este puente hace el camino de vuelta:
recoge las tres versiones y se las da al agente para que las correlacione en un
solo incidente.

```
   monitoreo (bus :8010) ─┐
   dev-chat      (:8000) ─┼─▶  volcado marcado por canal  ─▶  agente (:8080)
   logs/semáforo (:8028) ─┘                                        │
                                                                    ▼
                                                          reporte en 5 secciones
```

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

**El volcado va troceado.** El agente acepta 20 mensajes de 4.000 caracteres
(`src/maas_demo/service.py`), y la señal de los tres canales no entra en uno
solo. Se parte por canal, cada bloque etiquetado con su origen. Si aun así no
entra, se recorta **declarando** cuántos bloques se omitieron — nunca en
silencio.

**Un canal caído no mata la corrida.** Se marca como "no disponible" en el
volcado, que es información útil para el agente: no es lo mismo "no hubo señal
en el chat" que "el chat no estaba".

**El texto entra marcado como dato.** El prefacio dice explícitamente que el
volcado es material a analizar y nunca instrucciones. Importa porque una de las
fuentes es un chat abierto donde cualquiera escribe lo que quiera.

**En `mock` el agente no analiza.** Devuelve una respuesta determinista con las 5
secciones correctas, que sirve para probar la plomería sin gastar cuota. El
análisis real necesita `MAAS_MODE=live` y la API key de MaaS.

**La verdad se imprime aparte.** Al final de cada corrida se muestra cuántos
incidentes hubo realmente (desde `GET /api/verdad` del bus), para contrastar con
lo que el agente detectó. El agente nunca ve esos datos.
