# rank_pr_importance.py

Consume el JSON de `read_pr_diff.py` y decide qué archivos merecen tokens del
modelo. Los que no superan el umbral no cuestan nada.

Envoltorio fino sobre `src/guardian/ranking.py` y `src/guardian/context.py`. La
ejecución completa del Caso 1 está en [`../../README.md`](../../README.md).

## Flujo

```text
Pull Request → read_pr_diff.py → pr_N.json → rank_pr_importance.py
                                                 ├── files_by_importance
                                                 ├── folders_by_importance
                                                 ├── llm_analysis_queue   (índice ≥ 50)
                                                 └── savings              (tokens antes/después)
```

## Uso

```bash
python rank_pr_importance.py pr_3.json
python rank_pr_importance.py pr_3.json --output pr_3_ranked.json
python rank_pr_importance.py pr_3.json --json
```

## Fórmula

`55%` formato · `30%` ubicación · `10%` tamaño del cambio · `5%` estado Git.

Las tablas de puntuación viven en `src/guardian/policies/importance.json`, no en
el código. Anclas de formato: `.env` y `.tfvars` 100, `.tf` y `Dockerfile` 98,
`.sql` 94, `.py` y `.ps1` 92, `.yaml` 88, `.json` 72, `.md` 18, binarios
generados 1. Anclas de carpeta: `security/` `auth/` `terraform/` 100, `infra/`
98, `database/` 96, `api/` `config/` 94, `src/` 90, `scripts/` 82, `tests/` 58,
`docs/` 20.

## Prioridades

```text
85-100  CRITICAL      70-84  HIGH      50-69  MEDIUM      30-49  LOW      0-29  MINIMAL
```

`llm_analysis_queue` contiene solo los archivos con índice `>= 50`, ordenados de
mayor a menor. El motor de reglas se aplica únicamente a esa cola.
