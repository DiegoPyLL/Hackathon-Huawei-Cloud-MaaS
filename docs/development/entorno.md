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
python3 scripts/ejecutablesBase/configurar-devkit-huawei.py
```

El comando valida Node.js y detecta cuáles clientes están disponibles, conserva
los otros servidores de ambos archivos, configura HuaweiCloud DevKit e instala
KooCLI. El objetivo predeterminado es `auto`; se puede seleccionar un cliente o
exigir ambos de forma explícita.

Opciones disponibles:

```bash
# Mostrar acciones sin instalar ni modificar archivos
python3 scripts/ejecutablesBase/configurar-devkit-huawei.py --dry-run

# Configurar solamente uno de los clientes MCP
python3 scripts/ejecutablesBase/configurar-devkit-huawei.py --target codex
python3 scripts/ejecutablesBase/configurar-devkit-huawei.py --target claude
python3 scripts/ejecutablesBase/configurar-devkit-huawei.py --target both

# Configurar tambien las credenciales de forma interactiva
python3 scripts/ejecutablesBase/configurar-devkit-huawei.py --auth

# Configurar solo MCP cuando KooCLI ya esta instalado o no se necesita
python3 scripts/ejecutablesBase/configurar-devkit-huawei.py --skip-koocli
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

Para usar inferencia real, copiar `.env.example` a `.env`, establecer
`MAAS_MODE=live` y completar `MAAS_API_KEY` con una clave `sk-...` de Kostra. El
modelo debe ser uno de los que la cuenta tiene habilitados; ver la tabla de
[`../architecture/stack.md`](../architecture/stack.md).

El saldo de Kostra es prepago y **compartido con la cuenta del chat web**: no hay
saldo de API aparte. Alguien usando el chat consume el mismo saldo que la demo.

## Variables de entorno

Copiar `.env.example` como `.env` y completar solo las variables necesarias.
`.env` es local y nunca debe agregarse a Git.

### Huawei Cloud (solo para las herramientas MCP)

- `HW_ACCESS_KEY`: access key del usuario IAM de Huawei Cloud.
- `HW_SECRET_KEY`: secret key correspondiente.
- `HW_REGION`: región del proyecto de Huawei Cloud.

### Inferencia (Kostra)

- `MAAS_API_KEY`: clave `sk-...` de Kostra, solo para el backend.
- `MAAS_MODE`: `mock` para demo local o `live` para inferencia real.
- `MAAS_BASE_URL`: URL base del proveedor. Por defecto `https://ai.kostra.cloud/v1`.
- `MAAS_MODEL`: identificador exacto del modelo. Respaldo de las tres variables por rol.
- `MAAS_MODELO_TRIAGE`: modelo del Orquestador en la fase de triage.
- `MAAS_MODELO_ESPECIALISTA`: modelo de DBA, SysAdmin y SecOps.
- `MAAS_MODELO_CONSOLIDACION`: modelo del Orquestador en la consolidación.
- `MAAS_TIMEOUT_SECONDS`: presupuesto máximo de la llamada al proveedor.

Las tres variables por rol usan por defecto el mejor modelo disponible: la calidad
va antes que el costo, y el triage además propaga sus errores hacia abajo. Existen
para que una evaluación pueda **demostrar** que algún rol tolera un modelo más
barato sin perder calidad — no para abaratar por defecto. Ver
[ADR-0003](../architecture/decisions/0003-orquestacion-multiagente.md).

### Almacén (Supabase)

- `SUPABASE_URL`: URL del proyecto.
- `SUPABASE_SERVICE_ROLE_KEY`: clave de servicio, **solo para el backend**.

La `service_role` **salta RLS por diseño**. No se registra en logs, no se versiona y
no llega al navegador bajo ninguna circunstancia: el navegador habla con nuestro
servidor, nunca con Supabase. Ver
[ADR-0005](../architecture/decisions/0005-supabase-como-almacen.md).

Nota sobre el prefijo: `MAAS_*` es un nombre heredado de cuando el proveedor iba a
ser Huawei MaaS. Hoy apunta a Kostra. El renombrado es deuda registrada en el
[ADR-0002](../architecture/decisions/0002-proveedor-de-inferencia-kostra.md).

### Lista blanca de `.env`

`dotenv.py` solo admite las variables de su lista blanca `ALLOWED_KEYS`, que abarca
los prefijos `MAAS_*` y `SUPABASE_*`. Una variable nueva no entra sola: hay que
añadirla ahí a propósito. Esa fricción es intencional.

No exponer ninguna de estas variables en el frontend ni incluir valores reales
en documentación, capturas, logs o comandos versionados.
