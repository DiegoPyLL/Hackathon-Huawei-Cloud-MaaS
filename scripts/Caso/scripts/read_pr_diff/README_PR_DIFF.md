# Lectura de diff desde un Pull Request

Este script obtiene directamente desde GitHub:

- Metadata del Pull Request.
- Branch origen y destino.
- Archivos modificados.
- Cantidad de additions/deletions.
- Diff completo.
- Payload JSON preparado para un agente LLM.

## Instalación

```bash
pip install -r requirements-pr-diff.txt
```

## Token de GitHub

Para repositorios privados:

```bash
export GITHUB_TOKEN="github_pat_..."
```

Para repositorios públicos el token puede ser opcional, aunque GitHub aplica límites de API más estrictos sin autenticación.

## Uso

```bash
python read_pr_diff.py \
  --repo DiegoPyLL/Hackathon-Huawei-Cloud-MaaS \
  --pr 12
```

Salida JSON:

```bash
python read_pr_diff.py \
  --repo DiegoPyLL/Hackathon-Huawei-Cloud-MaaS \
  --pr 12 \
  --json
```

Guardar payload:

```bash
python read_pr_diff.py \
  --repo DiegoPyLL/Hackathon-Huawei-Cloud-MaaS \
  --pr 12 \
  --output pr_12.json
```

## Integración con el agente

El campo más importante es:

```json
{
  "diff": "...",
  "files": [],
  "pull_request": {},
  "summary": {}
}
```

Este payload puede enviarse directamente al backend encargado de consultar Huawei Cloud MaaS.

## Control de tokens

Por defecto el diff se limita a 60000 caracteres.

Puede cambiarse:

```bash
python read_pr_diff.py \
  --repo DiegoPyLL/Hackathon-Huawei-Cloud-MaaS \
  --pr 12 \
  --max-chars 30000
```

Para un sistema de producción conviene filtrar primero los archivos relevantes de infraestructura antes de enviarlos al LLM.
