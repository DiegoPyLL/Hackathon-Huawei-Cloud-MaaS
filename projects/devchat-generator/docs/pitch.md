# Guion de Pitch — Incident Triage Agent

## Duración: 5 minutos

---

### Slide 1: Título (15s)

**Incident Triage Agent**
Un agente que recibe señal de tres canales (email, monitoring, dev chat),
la clasifica, correlaciona y devuelve un incidente consolidado con severidad,
dueño y referencia a incidentes previos.

> "Cuando algo se rompe en producción, la señal llega por todos lados a la
> vez: un email de un cliente, una alerta de monitoring, alguien gritando
> en el dev chat. Hoy, un humano tiene que juntar las piezas. Este agente
> lo hace."

---

### Slide 2: El problema (30s)

- Un incidente real genera señal en **3 canales simultáneamente**.
- Cada canal cuenta una parte de la historia:
  - **Dev chat**: primera señal, pero mucho ruido.
  - **Monitoring**: estructurada, pero sin contexto humano.
  - **Email**: formal, pero prioridad declarada ≠ severidad real.
- **Nadie correlaciona**: el mismo incidente genera 3 tickets duplicados.
- El on-call pierde 15-20 min solo en juntar contexto antes de actuar.

---

### Slide 3: Qué hace el agente (60s)

**Un agente, un loop, tres pasos:**

1. **Clasificar** — cada señal contra una taxonomía canónica de 8 tipos.
   - Modelo barato (DeepSeek V4 Flash) para esta parte.
   - Regla crítica: severidad por impacto, no por tono ni prioridad declarada.

2. **Buscar similares** — RAG sobre incidentes previos (KB).
   - "Esto ya pasó, así se arregló."
   - Retrieval por servicio + categoría + overlap de keywords.

3. **Consolidar** — resumen ejecutivo + causa raíz + acciones recomendadas.
   - Modelo fuerte (Qwen3-32B) solo para esta parte.
   - Aquí vive el valor: el incidente listo para actuar.

**Correlación cross-canal**: si dos señales del mismo servicio y categoría
llegan dentro de 30 min, se marcan como duplicado.

---

### Slide 4: Arquitectura (45s)

```
Email ─┐
Monitoring ─┼─→ Agent Loop ──→ Incidente Consolidado
Dev Chat ─┘        │
                    ├─ classify (DeepSeek V4 Flash)
                    ├─ search KB (RAG, sin LLM)
                    └─ consolidate (Qwen3-32B)
```

- **Huawei Cloud MaaS** — API compatible OpenAI, modelos en Hong Kong.
- **Model routing** — barato para clasificar, fuerte solo para resumen.
  MaaS reduce costo 50-80% vs. alternativas premium.
- **Taxonomía canónica** — 8 tipos de incidente + 2 buckets no-incidente
  (solicitud, ruido). Sin los buckets de no-incidente, el agente infla
  sus propias métricas.

---

### Slide 5: Demo en vivo (90s)

1. Levantar el simulador de dev chat (ya corriendo en :8000).
2. Abrir la demo del agente en :8001.
3. Presionar "Ejecutar Triage".
4. Mostrar cómo:
   - Una alerta de monitoring + un email + un thread de dev chat del mismo
     servicio se correlacionan en un solo incidente.
   - El agente encuentra el incidente previo en la KB y recomienda la
     solución que funcionó antes.
   - Una señal de "solicitud" o "ruido" se clasifica correctamente como
     no-incidente (no infla métricas).

---

### Slide 6: Prevención de alucinaciones (30s)

- **Severidad por impacto, no por lenguaje.** El prompt explicita que tono
  y prioridad declarada no determinan severidad. El generador sintético
  prueba esto: `tono_percibido` es independiente de `severidad_real`.
- **Buckets de no-incidente.** Solicitud y ruido existen como categorías
  explícitas. El agente puede decir "esto no es un incidente".
- **RAG con score.** Las referencias a incidentes previos incluyen score
  de similitud. Si no hay match, no se inventa.
- **Confianza reportada.** Cada incidente incluye un score de confianza.

---

### Slide 7: Costo y ROI (30s)

- **Model routing**: DeepSeek V4 Flash (barato) para clasificar/deduplicar,
  Qwen3-32B (fuerte) solo para resumen final.
- MaaS reduce costo 50-80% vs. alternativas premium.
- 3 llamadas por señal (classify + consolidate + opcional), no 10.
- KB search sin LLM (keyword overlap) — costo cero.

---

### Slide 8: Cierre (15s)

> "Un agente que no solo detecta incidentes, sino que los consolida,
> correlaciona y te dice cómo se arregló la última vez. En 6 horas,
> con modelos de Huawei Cloud MaaS."

---

## Notas para la demo

- Tener el simulador de dev chat corriendo en :8000 antes de empezar.
- La demo del agente en :8001.
- Si la latencia de MaaS es alta (Hong Kong), usar el modo "lento" del
  simulador y procesar solo 10-15 señales para que la demo no se eternice.
- Plan B: si MaaS no responde, tener screenshots del output guardados.
