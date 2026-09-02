# read_pr_diff.py

Descarga un Pull Request de GitHub a un JSON, con el **patch de cada archivo por
separado**. Ese formato es lo que permite que el ranking de importancia recorte
de verdad lo que se envía al modelo.

Envoltorio fino sobre `src/guardian/github.py`. La ejecución completa del Caso 1
está en [`../../README.md`](../../README.md).

## Token de GitHub

```bash
export GITHUB_TOKEN="github_pat_..."
```

Opcional en repositorios públicos (con límites de API más estrictos).
Obligatorio para repositorios privados y para publicar el veredicto.

## Uso

```bash
python read_pr_diff.py --repo DiegoPyLL/Hackathon-Huawei-Cloud-MaaS --pr 3 --output pr_3.json
```

| Flag | Efecto |
|---|---|
| `--repo owner/repository` | Repositorio. Obligatorio. |
| `--pr N` | Número del Pull Request. Obligatorio. |
| `--output archivo.json` | Guarda el payload. |
| `--json` | Imprime el payload completo por stdout. |
| `--max-patch-chars N` | Trunca cada patch individual. Default: 12000. |

## Salida

```json
{
  "repository": "owner/repo",
  "pull_request": { "number": 3, "head_sha": "...", "...": "..." },
  "summary": { "changed_files": 26, "additions": 1209, "deletions": 55 },
  "files": [
    { "filename": "...", "status": "added", "patch": "@@ ... @@", "patch_truncated": false }
  ]
}
```

El siguiente paso es `rank_pr_importance.py`, que decide qué `files[*].patch`
llegan al modelo.
