# Incident Triage Agent — AI Agentic Hackathon (Huawei Cloud MaaS)

## Evento
- AI Agentic Hackathon, 03.Septiembre.2026, organiza Kostra con Huawei Cloud como partner tecnológico.
- Build: 09:45–13:00 y 14:00–17:00 (6h15 reales). Code freeze 17:00. Pitches 17:10. Ganadores 18:30.
- El desafío se revela en el kickoff (09:30), no está publicado de antemano.

## Qué estamos construyendo
Un agente de triage de incidentes que recibe señal de tres canales (ticket email,
alerta de monitoring, dev chat), la clasifica contra una taxonomía canónica,
correlaciona/deduplica, y devuelve un incidente consolidado con severidad,
dueño sugerido y referencia a incidentes previos similares (RAG).

## Stack y decisiones técnicas
- Huawei Cloud MaaS, API compatible con OpenAI (cambiar `base_url` + `api_key`).
- Modelos disponibles: DeepSeek V3.2, Qwen3-32B, Zhipu GLM-5. Verificar tool calling
  en cada uno antes del día del evento, no asumir paridad.
- Inferencia corre en Hong Kong (nodos Ascend) → latencia real desde Chile.
  Diseñar con pocas llamadas encadenadas y usar streaming en la demo.
- Model routing como argumento de costo para el pitch: modelo barato para
  clasificar/deduplicar, modelo fuerte solo para resumen y recomendación final.
  MaaS reduce costo 50–80% vs. alternativas premium — cuantificar esto en la slide.
- Un agente, un loop, pocas tools. No sobrediseñar multiagente en 6 horas.

## Estado actual
- [x] Generador sintético de dev chat (`channels/devchat/generator/`)
- [ ] Generador sintético de email
- [ ] Generador sintético de monitoring alert
- [ ] Esquema canónico de incidente (formato de salida del clasificador)
- [ ] Loop del agente con tool calling sobre MaaS
- [ ] Lógica de correlación/deduplicación cross-canal
- [ ] Demo UI mínima
- [ ] Guion de pitch

Ver `docs/taxonomia_incidentes.md` para la clasificación y `channels/*/NOTES.md`
para las particularidades de cada canal.

## Plan del día
- 09:30–10:00: no escribir código. Definir alcance + guion literal de la demo.
- 12:00: esqueleto end-to-end funcionando, aunque sea feo.
- 14:00: alguien deja de tocar código y empieza slides, no vuelve atrás.
- 15:30: code freeze de facto, solo pulido.
- 16:00–17:00: dos ensayos completos + grabar video de respaldo de la demo.

## Riesgo #1
Acceso: cuenta Huawei Cloud, activación MaaS, API key, cuota. Resolver ANTES
del día del evento, no el 3 de septiembre.
