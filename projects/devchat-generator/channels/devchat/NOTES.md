# Canal: Dev Chat

## Lo que llega
Cubre casi toda la taxonomía, con dos particularidades: suele ser la
**primera señal** (antes que el monitoring), y trae discusión de incidentes
ya abiertos, no solo aperturas nuevas.

## Cómo llega
Fragmentado en múltiples mensajes y threads, contexto repartido en las
respuestas, jerga interna, sin dueño declarado explícitamente.

## Qué debe hacer el agente
1. Decidir primero **si hay incidente**. Este es el canal con peor relación
   señal-ruido de los tres — más falsos positivos que ningún otro.
2. Delimitar la ventana de mensajes que constituye el evento.
3. Detectar si alguien ya está trabajando en él (evitar duplicar ownership).

## Oportunidad: mitigación histórica
Los mensajes de resolución de incidentes pasados son la mejor fuente para
"esto ya pasó, así se arregló". Barato de implementar con retrieval sobre
`data/kb_incidentes_previos.jsonl`. Es el movimiento de demo con mejor
relación esfuerzo/impacto: correlación cross-fuente + resumen ejecutivo +
link al incidente similar.

## Generador sintético
`generator/generate_devchat_tickets.py` — genera hilos con groundtruth
(`categoria_real`, `es_incidente`, `severidad_real`, `tono_percibido`) para
medir precisión del clasificador contra algo objetivo.

Uso:
```
python3 generator/generate_devchat_tickets.py --n 60 --seed 7 \
  --out data/dev_chat_tickets.jsonl \
  --kb-out data/kb_incidentes_previos.jsonl
```

Campos de groundtruth relevantes para evaluación:
- `tono_percibido` es independiente de `severidad_real` a propósito — prueba
  si el clasificador está infiriendo severidad del lenguaje (no debería).
- ~16% de los hilos son `solicitud` o `ruido` (no incidente) — mide falsos
  positivos.
- ~30% de los incidentes referencian un `INC-XXXX` de la KB.

## Limitación conocida
Cuando no hay incidente previo del mismo servicio en la KB, el generador cae
a uno aleatorio y la referencia puede no calzar temáticamente. Es realista
(la gente también referencia mal a veces), pero si estorba para la demo de
RAG, filtrar también por categoría en `build_thread()`.

## Pendiente
- [ ] Hilos multi-incidente (dos problemas distintos mezclados en el mismo
      canal) — es lo que rompe a los clasificadores ingenuos, útil como
      caso de prueba adicional antes del evento.
