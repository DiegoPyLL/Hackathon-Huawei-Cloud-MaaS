# Canal: Monitoring

## Lo que llega
Alertas de sistemas de monitoring (Prometheus, Datadog, CloudWatch). La señal
más estructurada de los tres canales: métricas, thresholds, labels, runbook
link. Cubre principalmente indisponibilidad, degradación, capacidad y seguridad
— rara vez error funcional o datos.

## Cómo llega
Una alerta por evento, con labels (service, severity, environment), métrica
que disparó, valor actual vs threshold, y timestamp. No hay ambigüedad sobre
si es incidente — si disparó una alerta, algo pasó. El ruido viene de alertas
recuperadas (flapping) y duplicados.

## Qué debe hacer el agente
1. Mapear la alerta a la taxonomía canónica (más directo que dev chat).
2. La severity de la alerta suele ser confiable (viene de SLO/SLI config),
   pero validar contra impacto real.
3. Deduplicar alertas flapping (misma alerta disparándose y recuperándose).

## Generador sintético
`generator/generate_monitoring_alerts.py` — genera alertas con groundtruth
(`categoria_real`, `es_incidente`, `severidad_real`, `alert_state`) para
medir precisión del clasificador.

`alert_state` puede ser `firing` o `resolved` — las `resolved` son ruido
(alerta que se recuperó sola, no requiere acción).

Uso:
```
python generate_monitoring_alerts.py --n 40 --seed 7 \
  --out data/monitoring_alerts.jsonl
```

## Pendiente
- [ ] Alertas correlacionadas (mismo incidente, múltiples métricas) —
      útil para probar deduplicación.
