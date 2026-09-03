![alt text](image.png)

# Incident Response Brief

Vertical slice para Huawei Cloud ModelArts Studio (MaaS): un Incident Response
Agent que investiga logs sintéticos con ruido y falsos positivos, cita
evidencia concreta para su causa raíz y propone una corrección, mediante una
experiencia web con streaming, métricas y modo de ejecución visible.

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

Abrir <http://127.0.0.1:8080>.

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
```

El último comando falla si el despliegue responde en `mock`; así una simulación
no puede presentarse accidentalmente como integración real.


## Arquitectura

```text
Navegador
   │ POST /api/chat/stream (SSE)
   ▼
ChatService ── contrato propio ──┬── MockProvider (local y determinista)
                                 └── MaaSProvider (Huawei MaaS V2)
```

El dominio no conoce URLs, autenticación ni eventos del proveedor. El adaptador
traduce el contrato de Huawei y preserva TLS. La respuesta final expone modo,
modelo y latencia.

## Estructura

```text
src/maas_demo/      Aplicación, proveedor MaaS y frontend
tests/              Contratos, streaming y API HTTP
evals/              Casos repetibles de evaluación
scripts/            Instalación, evaluación y smoke test
docs/product/       Visión, alcance y guion de demo
docs/architecture/  Stack y decisiones técnicas
docs/operations/    Despliegue y comprobación live
```

## Estado

- Vertical slice local: operativo en modo `mock`.
- Adaptador Huawei MaaS V2: implementado y probado con contrato simulado.
- Llamada cloud real: requiere una API key MaaS y servicio habilitado.
- Despliegue público: pendiente de elegir y aprovisionar el runtime Huawei.

La visión y lo que queda explícitamente fuera están en
[`docs/product/vision.md`](docs/product/vision.md) y
[`docs/product/alcance.md`](docs/product/alcance.md).
