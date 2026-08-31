# Instrucciones del proyecto

## Objetivo

Construir un vertical slice de Huawei MaaS demostrable y medible. La prioridad
es completar una tarea real de extremo a extremo; no ampliar la arquitectura sin
que el componente nuevo participe en la demo.

## Invariantes

- `mock` y `live` siempre son visibles. Nunca convertir un fallo `live` en éxito
  `mock` silencioso.
- `MAAS_API_KEY` solo vive en backend y nunca se imprime, versiona ni envía al
  navegador.
- El dominio depende del contrato `ChatProvider`, no de payloads o URLs Huawei.
- Todo cambio de prompt o proveedor se compara con `evals/cases.json`.
- Precios, modelos, regiones, cuotas y endpoints Huawei son volátiles: comprobar
  documentación oficial o HuaweiCloud DevKit antes de decidir.
- No crear, modificar o eliminar recursos cloud sin mostrar el plan exacto y
  obtener autorización explícita.

## Verificación mínima

```bash
python3 -m unittest discover -s tests -v
python3 scripts/evaluar.py --mode mock
```

Para afirmar que la integración real funciona también debe pasar:

```bash
python3 scripts/evaluar.py --mode live
python3 scripts/prueba-humo.py --url URL --require-mode live
```

## Fuentes del repositorio

1. `docs/product/`: problema, alcance y demo.
2. `docs/architecture/`: estado técnico y ADR.
3. `docs/development/`: entorno y pruebas.
4. `.claude/skills/genai/` y `.claude/skills/cloud/`: criterio transversal.
