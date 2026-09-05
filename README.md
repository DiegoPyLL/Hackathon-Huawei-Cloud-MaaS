<p align="center">
  <a href="https://www.huaweicloud.com/intl/en-us/" target="_blank" rel="noopener noreferrer">
    <img src="image.png" alt="Huawei Cloud" height="150">
  </a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://ai.kostra.cloud/" target="_blank" rel="noopener noreferrer">
    <img src="image-1.png" alt="Kostra Cloud" height="150">
  </a>
</p>


# Incident Response Agent

Vertical slice para Huawei Cloud ModelArts Studio (MaaS), usando los servicios de
[Kostra Cloud](https://ai.kostra.cloud/) como proveedor de modelos: un agente que recibe un
incidente, separa el ruido y los falsos positivos, identifica una causa raíz con
evidencia concreta y propone una respuesta. La experiencia web muestra el
progreso en streaming, las métricas y el modo de ejecución.

El agente trabaja sobre datos mockeados de una empresa ficticia: logs, tickets,
alertas, cuentas, sesiones, hosts y transacciones simuladas. Esto permite
demostrar el diagnóstico y el flujo de respuesta sin intervenir sistemas ni datos
reales.

Todos los procesos de inferencia del vertical —triage, especialistas y
consolidación— usan por defecto el modelo **GLM 5.2** a través de Kostra Cloud.
El modelo puede cambiarse mediante variables de entorno para evaluación, sin
cambiar el contrato del dominio.

El mismo flujo puede recibir incidentes desde tres canales: chat de desarrollo,
correo de soporte y monitoreo. El subproyecto [`projects/incident-agent/`](projects/incident-agent/)
añade el flujo de tickets por correo: Gmail reenvía a Postmark, Postmark entrega
el webhook a Supabase y el incidente queda disponible para el agente. También
incluye la generación de borradores de respuesta; el envío efectivo del correo
queda fuera del vertical actual.

El objetivo actual no es fingir un producto terminado, sino demostrar en pocos
minutos que la integración completa funciona y se puede evaluar.

## Clonar el repo de skills 

La biblioteca de skills vive en `.claude/skills` como submódulo git. Tras clonar
el repositorio:

```bash
git submodule add https://github.com/DiegoPyLL/FullSkills.git .claude/skills
git submodule update --init --recursive
```

## Luego instalar HuaweiCloud DevKit

La configuración MCP compartida está disponible para Codex en
[`.codex/config.toml`](.codex/config.toml) y para Claude Code en
[`.mcp.json`](.mcp.json). 

# *Requiere Node.js 22 o superior*

```bash
# Detectar, configurar y comprobar los clientes instalados
python3 scripts/ejecutablesBase/configurar-devkit-huawei.py

# Configurar credenciales mediante el flujo interactivo de Huawei
python3 scripts/ejecutablesBase/configurar-devkit-huawei.py --auth

# Trabajar solamente con uno de los clientes
python3 scripts/ejecutablesBase/configurar-devkit-huawei.py --target codex
python3 scripts/ejecutablesBase/configurar-devkit-huawei.py --target claude

# Exigir que ambos clientes estén instalados
python3 scripts/ejecutablesBase/configurar-devkit-huawei.py --target both
```

Consulta [`docs/development/entorno.md`](docs/development/entorno.md) para el
procedimiento completo. Claude Code solicita aprobar el servidor MCP compartido
la primera vez. Nunca se versionan `.env` ni credenciales reales.

## Ejecutar el panel

```bash
python3 -m src.maas_demo
```

Abrir <http://127.0.0.1:8080>. Eso levanta **solo el agente**, que es útil para
pegarle un volcado a mano.

## Ejecutar el sistema completo

El agente por sí solo no demuestra correlación: hace falta que la señal venga de
canales distintos, como en la realidad. Un comando levanta las seis piezas:

```bash
python3 projects/bus-incidentes/levantar_todo.py          # live
python3 projects/bus-incidentes/levantar_todo.py --mock   # sin gastar cuota
```

| Puerto | Qué es |
| --- | --- |
| 8010 | Bus de incidentes. Fuente de verdad, sin UI |
| 8000 | Dev chat: el equipo comenta los incidentes entre charla normal |
| 8028 | Semáforo de servicios y consola de logs |
| 8001 | Los tres canales alimentando al agente, con la cola de acciones propuestas |
| 8080 | El Incident Response Agent |
| 8020 | Trazabilidad: linaje de cada problema y conversión contra la verdad |

Una corrida de punta a punta, que recoge los tres canales y los correlaciona:

```bash
python3 projects/agente-puente/puente.py
```

El guion completo, paso a paso, está en [`DEMO.md`](DEMO.md).

## Llegar y correr

```bash
./scripts/ejecutablesBase/iniciar-demo.sh
```

Levanta el panel (`mock` si no hay `.env` con `MAAS_MODE=live`, `live` si lo
hay) y abre el navegador solo. `Ctrl+C` para detenerlo. En un file manager con
soporte de ejecución, doble click también funciona.

## Demo en menos de dos minutos

No requiere dependencias Python ni credenciales:

```bash
MAAS_MODE=mock python3 -m src.maas_demo
```

Abrir <http://127.0.0.1:8080>. La interfaz mostrará claramente `MOCK`.

Para ejecutar contra Huawei MaaS:

```bash
cp .env.example .env
# Completar MAAS_API_KEY y cambiar MAAS_MODE=live
python3 -m src.maas_demo
```

La aplicación nunca cambia silenciosamente de `live` a `mock`. Si Huawei MaaS
falla, la demo muestra el error.

## Evidencia verificable

```bash
# Pruebas unitarias y de integración HTTP
python3 -m unittest discover -s tests -v

# Dataset mínimo determinista
python3 scripts/ejecutablesBase/evaluar.py --mode mock

# Con el servidor iniciado
python3 scripts/ejecutablesBase/prueba-humo.py --require-mode mock

# Antes de presentar evidencia cloud real
python3 scripts/ejecutablesBase/evaluar.py --mode live
python3 scripts/ejecutablesBase/prueba-humo.py --url https://URL-DESPLEGADA --require-mode live

# Verificación completa en un comando: árbol limpio, sin secretos versionados,
# suite en verde, el número de tests no bajó, y el flujo corre en mock
python3 scripts/ejecutablesBase/compuerta.py

# Puntuación repetible sobre varios escenarios, con el stack levantado.
# Contrasta contra un groundtruth que el agente nunca ve.
python3 scripts/ejecutablesBase/puntuar.py --escenarios 6
```

El último comando falla si el despliegue responde en `mock`; así una simulación
no puede presentarse accidentalmente como integración real.


## Qué hace el agente

1. **Ingesta:** valida el tamaño, marca el canal de origen y trata el texto
   recibido como datos, no como instrucciones.
2. **Triage:** el Orquestador clasifica los incidentes en una taxonomía cerrada
   de ocho tipos y registra qué señales descartó:
   `indisponibilidad`, `degradacion`, `error_funcional`, `acceso_identidad`,
   `datos`, `integracion_terceros`, `capacidad` y `seguridad`.
3. **Despacho:** rutea cada incidente a uno o más especialistas: DBA, SysAdmin
   y SecOps. Las tareas se ejecutan en paralelo de forma acotada.
4. **Consolidación:** el Orquestador reúne los hallazgos y genera un reporte con
   tipo, causa raíz probable, evidencia, hipótesis descartadas y acción
   correctiva.
5. **Aprobación humana:** las acciones de riesgo quedan pendientes. Solo una
   persona puede aprobarlas o rechazarlas; el modelo nunca ejecuta SQL libre ni
   afirma que aplicó un cambio sin evidencia.

Una corrida incompleta se declara como parcial: los incidentes diferidos por
presupuesto y las tareas fallidas permanecen visibles.

## Arquitectura

```text
Navegador
   │ POST /api/chat/stream (SSE)
   ▼
ChatService / Orchestrator ── contrato ChatProvider ──┬── MockProvider (local)
                                                      └── MaaSProvider (live)
                                                               │
                                                               ▼
                                                        Kostra Cloud
                                                        (GLM 5.2)

Correo de soporte → Gmail → Postmark Inbound → Edge Function Supabase
                                                └→ tickets e incidentes
```

El dominio no conoce URLs, autenticación ni eventos del proveedor. El adaptador
traduce el contrato del proveedor y preserva TLS. La respuesta final expone modo,
modelo y latencia. En `mock` no se consume cloud; en `live`, un fallo del
proveedor se muestra como fallo y nunca se convierte silenciosamente en `mock`.

## Estructura

```text
src/maas_demo/           Aplicación, proveedor MaaS y frontend
tests/                   Contratos, streaming y API HTTP
evals/                   Casos repetibles de evaluación
scripts/                 Instalación, evaluación, compuerta y puntuación
projects/bus-incidentes/ Bus: un incidente, varios canales que lo cuentan distinto
projects/agente-puente/  Recoge los canales, corre al agente y lo puntúa (:8020)
projects/incident-agent/ Tickets por correo, schema Supabase y borradores de email
reinforcement-range/     Rango de pruebas aislado: contenedor vulnerable +
                         agente de hardening con shell real (ver ADR 0002)
docs/product/            Visión, alcance y guion de demo
docs/architecture/       Stack y decisiones técnicas
docs/operations/         Despliegue y comprobación live
```

## Tickets por correo (`projects/incident-agent/`)

Este módulo contiene el schema de Supabase, las Edge Functions `recibir-email` y
`generar-email`, además de datos semilla para probar el flujo. El esquema separa
correos entrantes, incidentes, hallazgos, trazas, aprobaciones y borradores de
salida. La clave `service_role` solo debe vivir en el backend.

Para aplicar o desplegar recursos externos se debe seguir el README del módulo y
autorizar explícitamente cada operación. En este clon, la integración del correo
está documentada y el código de las funciones está presente, pero la clasificación
automática del correo y el despacho del agente desde la Edge Function siguen en
desarrollo.

## Rango de refuerzo (`reinforcement-range/`)

Subsistema separado del Incident Response Agent — no comparte su invariante
de solo-lectura. Un contenedor Docker aislado (sin salida a internet) corre
una app deliberadamente vulnerable; un agente con `run_shell` y
`restart_target` reales intenta reforzarla, y el equipo la ataca a ciegas
para validar si aguanta. Detalle completo de arquitectura y decisiones en
[`docs/architecture/decisions/0002-rango-de-refuerzo-con-ejecucion-real.md`](docs/architecture/decisions/0002-rango-de-refuerzo-con-ejecucion-real.md).

```bash
cd reinforcement-range
bash reset.sh          # levanta el objetivo desde cero
bash run-harden.sh      # deja al modelo reforzarlo con shell real
python3 watch-and-defend.py  # el Incident Response Agent analiza el tráfico en vivo
```

Los `transcript-*.json` y `state*.json` no se versionan a propósito — son
spoilers del ataque a ciegas del equipo.

## Estado

- **Operativo:** panel web local en `mock`, endpoint de chat, ejecución
  multiagente de incidentes, streaming SSE, evaluación determinista y smoke test.
- **Implementado:** adaptador `live` compatible con la API de inferencia, contrato
  `ChatProvider`, persistencia opcional en Supabase y cola de aprobación humana.
- **En desarrollo:** clasificación automática de correos, ejecución del agente
  disparada por el webhook y envío efectivo de respuestas por email.
- **Requiere configuración:** una API key y un servicio MaaS habilitado para
  `live`; un proyecto Supabase para persistencia; y un runtime Huawei para un
  despliegue público.

La visión y lo que queda explícitamente fuera están en
[`docs/product/vision.md`](docs/product/vision.md) y
[`docs/product/alcance.md`](docs/product/alcance.md).
