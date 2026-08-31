# Entorno de desarrollo

## Requisitos

- Python 3.10 o superior.
- Node.js 22 o superior, instalado en el mismo entorno donde se ejecutan los
  clientes MCP.
- Codex CLI, Claude Code o ambos con acceso al proyecto.
- Una cuenta de Huawei Cloud. Para operaciones reales, usar un usuario IAM
  exclusivo para el hackathon y con permisos minimos.

## HuaweiCloud DevKit

El proyecto conecta Codex y Claude Code con HuaweiCloud DevKit mediante el mismo
servidor MCP. La configuración compartida está declarada en
[`.codex/config.toml`](../../.codex/config.toml) para Codex y
[`.mcp.json`](../../.mcp.json) para Claude Code. La versión del paquete está
fijada para que todos los integrantes utilicen las mismas herramientas.

Desde la raiz del repositorio:

```bash
python3 scripts/configurar-devkit-huawei.py
```

El comando valida Node.js y detecta cuáles clientes están disponibles, conserva
los otros servidores de ambos archivos, configura HuaweiCloud DevKit e instala
KooCLI. El objetivo predeterminado es `auto`; se puede seleccionar un cliente o
exigir ambos de forma explícita.

Opciones disponibles:

```bash
# Mostrar acciones sin instalar ni modificar archivos
python3 scripts/configurar-devkit-huawei.py --dry-run

# Configurar solamente uno de los clientes MCP
python3 scripts/configurar-devkit-huawei.py --target codex
python3 scripts/configurar-devkit-huawei.py --target claude
python3 scripts/configurar-devkit-huawei.py --target both

# Configurar tambien las credenciales de forma interactiva
python3 scripts/configurar-devkit-huawei.py --auth

# Configurar solo MCP cuando KooCLI ya esta instalado o no se necesita
python3 scripts/configurar-devkit-huawei.py --skip-koocli
```

La autenticación no lee `.env` ni acepta secretos como argumentos. Las
referencias `HW_ACCESS_KEY`, `HW_SECRET_KEY` y `HW_REGION` del archivo compartido
de Claude Code se resuelven desde el entorno y nunca contienen valores reales.

Después de la instalación, reiniciar cada cliente y ejecutar `/mcp`. Claude Code
pedirá aprobar el servidor definido por el proyecto la primera vez. La aprobación
del servidor no elimina las confirmaciones de sus herramientas con efectos. La
configuración también se puede comprobar desde la terminal:

```bash
codex mcp list
claude mcp list
```

## Aplicación

El modo local no necesita instalar paquetes:

```bash
MAAS_MODE=mock python3 -m src.maas_demo
```

Para usar Huawei MaaS, copiar `.env.example` a `.env`, establecer
`MAAS_MODE=live` y completar `MAAS_API_KEY`. El endpoint y modelo deben coincidir
con el servicio habilitado en la región real.

## Variables de entorno

Copiar `.env.example` como `.env` y completar solo las variables necesarias.
`.env` es local y nunca debe agregarse a Git.

- `HW_ACCESS_KEY`: access key del usuario IAM de Huawei Cloud.
- `HW_SECRET_KEY`: secret key correspondiente.
- `HW_REGION`: región del proyecto de Huawei Cloud.
- `MAAS_API_KEY`: API key de ModelArts Studio (MaaS), solo para el backend.
- `MAAS_MODE`: `mock` para demo local o `live` para Huawei MaaS real.
- `MAAS_BASE_URL`: URL base indicada por MaaS para la región habilitada.
- `MAAS_MODEL`: identificador exacto del modelo habilitado.
- `MAAS_TIMEOUT_SECONDS`: presupuesto máximo de la llamada al proveedor.

No exponer ninguna de estas variables en el frontend ni incluir valores reales
en documentación, capturas, logs o comandos versionados.
