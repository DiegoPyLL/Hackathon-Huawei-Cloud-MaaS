# Stack actual

| Pieza | Tecnología | Razón |
| --- | --- | --- |
| Runtime | Python 3.12, biblioteca estándar | Arranque desde clon limpio y superficie mínima |
| Servidor | `ThreadingHTTPServer` | Suficiente para el vertical slice; no se presenta como runtime productivo |
| Streaming | Server-Sent Events | Canal unidireccional simple para tokens y métricas |
| Inferencia | Huawei MaaS Standard API V2 | Contrato vigente con streaming y autenticación Bearer |
| Frontend | HTML, CSS y JavaScript nativos | Sin build ni dependencias para la demo |
| Evaluación | JSON + script Python | Casos versionados y ejecución local o live |
| Empaquetado | Docker | Artefacto portable para elegir runtime cloud después |

El endpoint, modelo, región, cuotas y precios no forman parte estable del stack:
se verifican en Huawei Cloud antes de cada despliegue. El valor por defecto actual
apunta a V2 en CN-Hong Kong porque la documentación consultada el 31-08-2026
limita esa API a dicha región.
