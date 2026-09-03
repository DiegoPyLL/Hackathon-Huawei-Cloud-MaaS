#!/usr/bin/env python3
"""
Genera el seed SQL de la bandeja de soporte a partir de los hilos de dev chat.

Cada correo es trazable a un hilo concreto de dev_chat_tickets.jsonl: el asunto
sale del primer mensaje, el cuerpo es la transcripcion del hilo y el groundtruth
del hilo (categoria_real, severidad_real, servicio_afectado) alimenta el ticket.
Nada se inventa: si el hilo no dice la causa raiz, el incidente queda sin ella.

Uso:
    python generar_seed_correos.py
    python generar_seed_correos.py --seguimientos 10 --salida /tmp/seed.sql
"""

import argparse
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DEVCHAT = RAIZ.parents[0] / "devchat-generator" / "channels" / "devchat" / "data"

DOMINIO_REMITENTE = "nortech.example"
CASILLA_SOPORTE = "soporte.jsonch@gmail.com"
LARGO_ASUNTO = 78

# El dataset usa dos categorias que no son incidente y por lo tanto nunca llegan
# al check de tipo_problema: "ruido" y "solicitud".
CATEGORIAS_NO_INCIDENTE = {"ruido", "solicitud"}


def leer_jsonl(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(linea) for linea in f if linea.strip()]


def sin_emojis(texto):
    """Deja solo caracteres imprimibles del plano basico: un asunto de correo."""
    return "".join(c for c in texto if c.isprintable() and ord(c) < 0x2000).strip()


def asunto_de(mensaje):
    texto = sin_emojis(mensaje["texto"])
    if len(texto) <= LARGO_ASUNTO:
        return texto
    return texto[: LARGO_ASUNTO - 3].rstrip() + "..."


def hora(timestamp):
    return timestamp[11:16]


def transcripcion(mensajes):
    return "\n".join(
        "[{}] {} ({}): {}".format(hora(m["timestamp"]), m["autor"], m["rol"], m["texto"])
        for m in mensajes
    )


def remitente_de(mensaje):
    return "{}@{}".format(mensaje["autor"], DOMINIO_REMITENTE)


def dificultad_por_largo(n_mensajes):
    if n_mensajes <= 3:
        return "facil"
    if n_mensajes <= 5:
        return "medio"
    return "dificil"


def estado_de(hilo):
    if hilo["hilo_resuelto_en_chat"]:
        return "resuelto"
    if len(hilo["mensajes"]) >= 4:
        return "en_progreso"
    return "abierto"


def verdad_de(hilo, kb):
    """Causa raiz y solucion, solo si el hilo o la KB las dicen."""
    if hilo["hilo_resuelto_en_chat"]:
        resolucion = hilo["mensajes"][-1]["texto"]
        return resolucion, resolucion
    previo = kb.get(hilo["id_incidente_previo_referenciado"])
    if previo:
        return previo["causa_raiz"], previo["solucion"]
    return None, None


def construir_correos(hilos, n_seguimientos):
    """Un correo por hilo, mas N seguimientos de los hilos mas largos."""
    correos = [
        {
            "message_id": "<{}@devchat.local>".format(h["thread_id"]),
            "thread_id": h["thread_id"],
            "canal": h["canal"],
            "remitente": remitente_de(h["mensajes"][0]),
            "asunto": asunto_de(h["mensajes"][0]),
            "cuerpo": transcripcion(h["mensajes"]),
            "recibido_en": h["timestamp_inicio"],
        }
        for h in hilos
    ]

    asuntos = {c["thread_id"]: c["asunto"] for c in correos}
    mas_largos = sorted(hilos, key=lambda h: (-len(h["mensajes"]), h["thread_id"]))
    for h in mas_largos[:n_seguimientos]:
        ultimo = h["mensajes"][-1]
        correos.append(
            {
                "message_id": "<{}-seg@devchat.local>".format(h["thread_id"]),
                "thread_id": h["thread_id"],
                "canal": h["canal"],
                "remitente": remitente_de(ultimo),
                "asunto": "Re: {}".format(asuntos[h["thread_id"]]),
                "cuerpo": transcripcion([ultimo]),
                "recibido_en": ultimo["timestamp"],
            }
        )

    correos.sort(key=lambda c: (c["recibido_en"], c["message_id"]))
    return correos


def construir_incidentes(hilos, kb):
    incidentes = []
    for h in hilos:
        if not h["es_incidente"] or h["categoria_real"] in CATEGORIAS_NO_INCIDENTE:
            continue
        causa, solucion = verdad_de(h, kb)
        incidentes.append(
            {
                "message_id": "<{}@devchat.local>".format(h["thread_id"]),
                "ticket": "INC-{:04d}".format(len(incidentes) + 1),
                "titulo": asunto_de(h["mensajes"][0]),
                "tipo": h["categoria_real"],
                "severidad": h["severidad_real"],
                "sistema": h["servicio_afectado"],
                "estado": estado_de(h),
                "dificultad": dificultad_por_largo(len(h["mensajes"])),
                "causa_raiz": causa,
                "solucion": solucion,
                "logs": [
                    "{} {}: {}".format(m["timestamp"], m["autor"], m["texto"])
                    for m in h["mensajes"]
                ],
            }
        )
    return incidentes


# --------------------------------------------------------------------------
# Emision del SQL
# --------------------------------------------------------------------------

def lit(valor):
    """Literal SQL: null, o texto con las comillas simples duplicadas."""
    if valor is None:
        return "null"
    return "'" + str(valor).replace("'", "''") + "'"


def fila(valores):
    return "(" + ", ".join(lit(v) for v in valores) + ")"


CABECERA = """\
-- ============================================================
-- Seed: bandeja de soporte derivada de los hilos de dev chat
--
-- ARCHIVO GENERADO. No editar a mano.
--   python projects/incident-agent/generator/generar_seed_correos.py
--
-- Cada correo viene de un hilo de dev_chat_tickets.jsonl: el cuerpo es la
-- transcripcion del hilo y el groundtruth del hilo define el ticket. Los correos
-- de categoria "ruido" y "solicitud", y los seguimientos, no generan incidente:
-- quedan procesados sin ticket, que es el registro de que se descartaron.
--
-- Uso:
--   supabase db execute -f projects/incident-agent/schema/seed_emails.sql
--   (o pegar el archivo completo en el SQL editor del proyecto)
--
-- Es idempotente: los UUID se derivan del message_id con md5.
--   email     -> md5(message_id)::uuid
--   incidente -> md5('inc:' || message_id)::uuid
--   saliente  -> md5('out:' || message_id)::uuid
-- ============================================================

-- ------------------------------------------------------------
-- 1) Correos entrantes crudos ({n_correos})
-- ------------------------------------------------------------
insert into emails_entrantes (id, message_id, remitente, asunto, cuerpo, headers, recibido_en)
select
  md5(v.mid)::uuid,
  v.mid,
  v.remitente,
  v.asunto,
  v.cuerpo,
  jsonb_build_object(
    'To', {casilla},
    'From', v.remitente,
    'X-Devchat-Thread', v.thread_id,
    'X-Devchat-Canal', v.canal,
    'X-Seed', 'devchat'
  ),
  v.recibido_en::timestamptz
from (values
"""

INCIDENTES = """\
) as v(mid, remitente, asunto, cuerpo, thread_id, canal, recibido_en)
on conflict (id) do nothing;

-- ------------------------------------------------------------
-- 2) Incidentes de los hilos marcados como incidente ({n_incidentes})
--
-- causa_raiz_real y solucion_esperada son la verdad de referencia; la vista
-- incidentes_agente no las expone. Quedan nulas cuando el hilo no dice la causa.
-- logs_adjuntos lleva los mensajes del hilo, citables uno a uno.
-- ------------------------------------------------------------
insert into incidentes (
  id, ticket_numero, titulo, descripcion, tipo_problema, severidad, sistema_afectado,
  estado, dificultad, canal_origen, origen_email_id, causa_raiz_real, solucion_esperada,
  logs_adjuntos, creado_en
)
select
  md5('inc:' || v.mid)::uuid,
  v.ticket,
  v.titulo,
  e.cuerpo,
  v.tipo,
  v.severidad,
  v.sistema,
  v.estado,
  v.dificultad,
  'email',
  e.id,
  v.causa_raiz,
  v.solucion,
  v.logs::jsonb,
  e.recibido_en + interval '12 minutes'
from (values
"""

CIERRE = """\
) as v(mid, ticket, titulo, tipo, severidad, sistema, estado, dificultad, causa_raiz, solucion, logs)
join emails_entrantes e on e.id = md5(v.mid)::uuid
on conflict (id) do nothing;

-- ------------------------------------------------------------
-- 3) Cerrar el circulo en los correos entrantes
-- ------------------------------------------------------------

-- Los que derivaron en ticket quedan enlazados.
update emails_entrantes e
set procesado = true,
    procesado_en = i.creado_en,
    incidente_id = i.id
from incidentes i
where i.origen_email_id = e.id
  and e.incidente_id is null;

-- El resto queda procesado y sin incidente: se evaluo y se descarto.
update emails_entrantes
set procesado = true,
    procesado_en = recibido_en + interval '20 minutes'
where headers->>'X-Seed' = 'devchat'
  and incidente_id is null
  and procesado = false;

-- ------------------------------------------------------------
-- 4) Borradores de respuesta para los incidentes ya atendidos
-- ------------------------------------------------------------
insert into emails_salientes (id, incidente_id, destinatario, asunto, cuerpo, estado, creado_en)
select
  md5('out:' || e.message_id)::uuid,
  i.id,
  e.remitente,
  '[' || i.ticket_numero || '] ' || i.titulo,
  'Hola,' || chr(10) || chr(10) ||
  'Registramos tu reporte como ' || i.ticket_numero || ' (' || i.severidad || ', ' || i.sistema_afectado || ').' || chr(10) ||
  'Estado actual: ' || i.estado || '.' || chr(10) || chr(10) ||
  'Te escribimos apenas haya novedades.' || chr(10) || chr(10) ||
  'Equipo de Soporte',
  'borrador',
  i.creado_en + interval '35 minutes'
from incidentes i
join emails_entrantes e on e.id = i.origen_email_id
where i.estado in ('en_progreso', 'resuelto')
on conflict (id) do nothing;

-- ------------------------------------------------------------
-- 5) Dejar la secuencia despues de los tickets del seed
-- ------------------------------------------------------------
select setval('incidentes_numero_seq', {n_incidentes}, true);
"""


def emitir_sql(correos, incidentes):
    filas_correos = ",\n".join(
        fila([c["message_id"], c["remitente"], c["asunto"], c["cuerpo"],
              c["thread_id"], c["canal"], c["recibido_en"]])
        for c in correos
    )
    filas_incidentes = ",\n".join(
        fila([i["message_id"], i["ticket"], i["titulo"], i["tipo"], i["severidad"],
              i["sistema"], i["estado"], i["dificultad"], i["causa_raiz"],
              i["solucion"], json.dumps(i["logs"], ensure_ascii=False)])
        for i in incidentes
    )
    return (
        CABECERA.format(n_correos=len(correos), casilla=lit(CASILLA_SOPORTE))
        + filas_correos
        + "\n"
        + INCIDENTES.format(n_incidentes=len(incidentes))
        + filas_incidentes
        + "\n"
        + CIERRE.format(n_incidentes=len(incidentes))
    )


def main():
    ap = argparse.ArgumentParser(description="Genera el seed SQL de correos desde los hilos de dev chat")
    ap.add_argument("--entrada", type=Path, default=DEVCHAT / "dev_chat_tickets.jsonl")
    ap.add_argument("--kb", type=Path, default=DEVCHAT / "kb_incidentes_previos.jsonl")
    ap.add_argument("--salida", type=Path, default=RAIZ / "schema" / "seed_emails.sql")
    ap.add_argument("--seguimientos", type=int, default=10, help="correos Re: de los hilos mas largos")
    args = ap.parse_args()

    hilos = sorted(leer_jsonl(args.entrada), key=lambda h: h["thread_id"])
    kb = {k["id"]: k for k in leer_jsonl(args.kb)}

    correos = construir_correos(hilos, args.seguimientos)
    incidentes = construir_incidentes(hilos, kb)

    args.salida.write_text(emitir_sql(correos, incidentes), encoding="utf-8")

    conteo = {}
    for i in incidentes:
        conteo[i["tipo"]] = conteo.get(i["tipo"], 0) + 1

    print(f"Generados {len(correos)} correos y {len(incidentes)} incidentes -> {args.salida}")
    print(f"Correos sin ticket: {len(correos) - len(incidentes)}")
    print("Distribucion por tipo de problema:")
    for tipo, n in sorted(conteo.items(), key=lambda x: -x[1]):
        print(f"  {tipo:22s} {n}")


if __name__ == "__main__":
    main()
