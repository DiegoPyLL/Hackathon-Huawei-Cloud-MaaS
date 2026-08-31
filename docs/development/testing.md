# Estrategia de pruebas

## Suite rápida

```bash
python3 -m unittest discover -s tests -v
```

Cubre configuración, `.env`, contrato del proveedor, parser SSE de MaaS,
validación del caso de uso y API HTTP real sobre un puerto efímero.

## Evaluación GenAI

```bash
python3 scripts/evaluar.py --mode mock
python3 scripts/evaluar.py --mode live --json-out evals/results/live.json
```

`mock` prueba determinismo y contrato. `live` mide el proveedor y modelo reales.
Los resultados no son intercambiables y siempre registran el modo.

Antes de cambiar prompt, modelo o parámetros, ejecutar el baseline y comparar los
mismos casos. El dataset inicial es pequeño y debe reemplazarse por casos del
dominio elegido antes de presentar calidad al jurado.

## Smoke test desplegado

```bash
python3 scripts/prueba-humo.py --url https://URL --require-mode live
```

La opción `--require-mode live` es obligatoria para afirmar que la integración
Huawei desplegada funciona.
