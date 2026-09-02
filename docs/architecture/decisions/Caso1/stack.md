# Stack actual

| Pieza | Tecnología | Razón |
| --- | --- | --- |
| Runtime | Python 3.12 | Arranque desde clon limpio y superficie mínima |
| Servidor | FastAPI y uvicorn | Tres endpoints con validación por esquema ([ADR 0002](decisions/0002-fastapi-guardian.md)) |
| Streaming | Server-Sent Events | Canal unidireccional simple para tokens y métricas |
| Inferencia | Huawei MaaS Standard API V2 | Contrato vigente con streaming y autenticación Bearer |
| Análisis de PR | Paquete `guardian`, solo biblioteca estándar | Ranking, reglas y coste son deterministas y auditables |
| Reglas y coste | JSON en `src/guardian/policies/` | Lo no negociable vive fuera del modelo |
| Frontend | HTML, CSS y JavaScript nativos | Sin build ni dependencias para la demo |
| Evaluación | JSON + pytest | Casos versionados y ejecución local o live |
| Empaquetado | Docker | Artefacto portable para elegir runtime cloud después |

El endpoint, modelo, región, cuotas y precios no forman parte estable del stack:
se verifican en Huawei Cloud antes de cada despliegue. El valor por defecto actual
apunta a V2 en CN-Hong Kong porque la documentación consultada el 31-08-2026
limita esa API a dicha región.
