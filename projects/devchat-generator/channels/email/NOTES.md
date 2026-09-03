# Canal: Email

## Lo que llega
Tickets de clientes o stakeholders externos. Estructura más formal que dev
chat: subject + body + metadata (remitente, prioridad declarada, categoría
del sistema de tickets). Cubre toda la taxonomía pero con menos ruido que
dev chat — la mayoría son incidentes reales o solicitudes.

## Cómo llega
Un mensaje por ticket, con subject y body. El subject suele ser la pista
más fuerte para clasificar. La prioridad declarada por el remitente **no**
es la severidad real — misma trampa que el tono en dev chat.

## Qué debe hacer el agente
1. Clasificar a partir de subject + body (no solo subject).
2. No inferir severidad de la prioridad declarada del ticket.
3. Extraer servicio afectado del cuerpo si está mencionado.

## Generador sintético
`generator/generate_email_tickets.py` — genera tickets con groundtruth
(`categoria_real`, `es_incidente`, `severidad_real`, `prioridad_declarada`)
para medir precisión del clasificador.

`prioridad_declarada` es independiente de `severidad_real` a propósito —
prueba si el clasificador está copiando la prioridad del ticket en vez de
calcular impacto real.

Uso:
```
python generator/generate_email_tickets.py --n 40 --seed 7 \
  --out data/email_tickets.jsonl
```

## Pendiente
- [ ] Tickets forward de threads de dev chat (mismo incidente, otro canal)
      — útil para probar correlación cross-canal.
