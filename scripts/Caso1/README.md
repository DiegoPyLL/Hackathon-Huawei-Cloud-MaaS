# Caso 1 — Brecha de seguridad en un Pull Request

> Actualizado: 02-09-2026

Primer caso de uso de **AI Cloud Deployment Guardian**. Un Pull Request titulado
"Brecha seguridad" introduce cambios que un revisor humano podría aprobar de un
vistazo pero que exponen credenciales y configuración insegura. El agente debe
bloquearlo, explicar por qué y dejar constancia en el propio Pull Request.

## Pull Request bajo prueba

| Campo | Valor |
|---|---|
| Repositorio | `DiegoPyLL/Hackathon-Huawei-Cloud-MaaS` |
| Número | [#3](https://github.com/DiegoPyLL/Hackathon-Huawei-Cloud-MaaS/pull/3) |
| Rama | `brecha-seguridad` → `main` |
| Archivos modificados | 26 (+1209 / −55) |

El cambio relevante es un archivo `.env` versionado con una clave real:

```env
MAAS_API_KEY=sk-...            # credencial funcional, ahora rotada
```

## Cómo se ejecuta

### Opción A — API (la del flujo real)

```bash
MAAS_MODE=live PYTHONPATH=src python -m maas_demo --port 8080
```

```bash
curl -X POST http://127.0.0.1:8080/api/guardian/analyze \
  -H "Content-Type: application/json" \
  -d '{"repository": "DiegoPyLL/Hackathon-Huawei-Cloud-MaaS", "pr": 3, "environment": "production"}'
```

Con `GITHUB_TOKEN` de escritura en el entorno, el veredicto se publica en el PR.
Para analizar sin escribir: añadir `"publish": false` al cuerpo.

### Opción B — scripts encadenados (para inspeccionar el recorte)

```bash
python scripts/Caso1/scripts/read_pr_diff/read_pr_diff.py \
  --repo DiegoPyLL/Hackathon-Huawei-Cloud-MaaS --pr 3 --output pr_3.json

python scripts/Caso1/scripts/rank_importancia_archivo/rank_pr_importance.py pr_3.json
```

`read_pr_diff.py` y `rank_pr_importance.py` son envoltorios finos sobre
`src/guardian/`; no contienen lógica propia y los reutilizarán los casos
siguientes.

## Resultado

### Veredicto

| | Valor |
|---|---|
| Decisión | **BLOCK** |
| Risk Score | 50/100 solo por reglas · 65 en la corrida `live` con hallazgos del modelo |
| Acción sugerida | `GENERATE_PATCH` |

Un `CRITICAL` del Rule Engine bloquea por sí solo, aunque no alcance la banda de
70: una credencial expuesta no se compensa con la ausencia de otros problemas.

### Hallazgos

| Severidad | Tipo | Origen | Política | Archivo |
|---|---|---|---|---|
| CRITICAL | `HARDCODED_SECRET` | Rule Engine | POLICY-SEC-002 | `.env` |
| MEDIUM | `SENSITIVE_FILE_COMMITTED` | LLM (solo `live`) | — | `.env` |

La regla detecta el patrón de credencial; el modelo añade el criterio de que el
`.env` no debería estar versionado en absoluto. El modelo no puede revertir el
veredicto de la regla, solo sumar contexto.

### Evidencia en GitHub

- Comentario: [pull/3#issuecomment-5513777670](https://github.com/DiegoPyLL/Hackathon-Huawei-Cloud-MaaS/pull/3#issuecomment-5513777670)
- Etiqueta aplicada: `guardian:block`

El comentario se actualiza en su sitio en cada ejecución (marca oculta
`<!-- ai-cloud-deployment-guardian -->`); no acumula uno por corrida. Solo queda
aplicada la etiqueta del veredicto vigente. El comentario nombra el archivo
`.env` pero nunca reproduce el valor de la credencial.

### Presupuesto de tokens

| Métrica | Valor |
|---|---:|
| Archivos enviados al modelo | 7 de 26 |
| Tokens de contexto | 2.514 |
| Tokens del diff completo | 6.072 |
| Llamadas al modelo | 1 |
| Lecturas de archivo bajo demanda | 0 |

Cola que llega al modelo, por índice de importancia:

```
90.20  CRITICAL  scripts/.../read_pr_diff/read_pr_diff.py
82.40  HIGH      .env
77.45  HIGH      scripts/ejecutablesBase/bootstrap.ps1
77.45  HIGH      scripts/ejecutablesBase/configurar-devkit-huawei.py
77.45  HIGH      scripts/ejecutablesBase/evaluar.py
77.45  HIGH      scripts/ejecutablesBase/prueba-humo.py
55.85  MEDIUM    scripts/.../read_pr_diff/requirements-pr-diff.txt
```

Los 19 archivos restantes (documentación, binarios generados, `.md`) no cuestan
ni un token. Las reglas deterministas se aplican solo a estos 7, de modo que la
documentación con ejemplos de configuración insegura no genera falsos positivos.

## Verificación automatizada

`tests/test_guardian_budget.py` usa `tests/fixtures/pr_3.json` (con la clave
redactada) y falla si:

- el contexto supera los 6.000 tokens,
- no recorta al menos a la mitad del diff completo,
- el veredicto de este PR deja de ser `BLOCK`,
- el secreto detectado deja de ser el de `.env`.

```bash
python -m pytest tests/test_guardian_budget.py tests/test_guardian_publish.py -q
```

## Notas

- `tests/fixtures/pr_3.json` es una captura del diff de PR #3 anterior a este
  renombrado, por lo que sus rutas todavía dicen `scripts/Caso/`. Es un snapshot
  histórico deliberado; no se regenera.
- La clave que este caso expuso fue **rotada** en Kostra. El commit sigue en el
  historial del repositorio público: borrar el archivo no habría bastado.
