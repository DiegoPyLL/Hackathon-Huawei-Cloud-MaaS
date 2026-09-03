import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL");
const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

if (!supabaseUrl || !supabaseServiceKey) {
  throw new Error("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY");
}

const supabase = createClient(supabaseUrl, supabaseServiceKey);

type Incident = {
  id: string;
  ticket_numero: string;
  titulo: string;
  descripcion: string;
  severidad: string;
  sistema_afectado: string;
  estado: string;
  origen_email_id?: string | null;
};

function buildEmail(incident: Incident, recipient: string) {
  const subject = `[${incident.ticket_numero}] Actualización de incidente: ${incident.titulo}`;
  const body = [
    `Hola,`,
    "",
    `Hemos registrado tu reporte con el ticket ${incident.ticket_numero}.`,
    "",
    `Incidente: ${incident.titulo}`,
    `Sistema afectado: ${incident.sistema_afectado}`,
    `Severidad: ${incident.severidad}`,
    `Estado actual: ${incident.estado}`,
    "",
    `Descripción registrada: ${incident.descripcion}`,
    "",
    "Nuestro equipo está revisando el caso. Te informaremos cuando haya avances.",
    "",
    "Saludos,",
    "Equipo de soporte",
  ].join("\n");

  return { recipient, subject, body };
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    });
  }

  let payload: { incidente_id?: string; destinatario?: string };
  try {
    payload = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "payload invalido, no es JSON" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (!payload || typeof payload !== "object" || !payload.incidente_id) {
    return new Response(JSON.stringify({ error: "incidente_id es obligatorio" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const { data: incident, error: incidentError } = await supabase
    .from("incidentes")
    .select("id, ticket_numero, titulo, descripcion, severidad, sistema_afectado, estado, origen_email_id")
    .eq("id", payload.incidente_id)
    .single();

  if (incidentError || !incident) {
    return new Response(JSON.stringify({ error: "incidente no encontrado" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  }

  let recipient = payload.destinatario;
  if (!recipient && incident.origen_email_id) {
    const { data: sourceEmail } = await supabase
      .from("emails_entrantes")
      .select("remitente")
      .eq("id", incident.origen_email_id)
      .single();
    recipient = sourceEmail?.remitente;
  }

  if (!recipient || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipient)) {
    return new Response(JSON.stringify({
      error: "No se pudo determinar un destinatario válido",
    }), {
      status: 422,
      headers: { "Content-Type": "application/json" },
    });
  }

  const email = buildEmail(incident, recipient);
  const { data: savedEmail, error: saveError } = await supabase
    .from("emails_salientes")
    .insert({
      incidente_id: incident.id,
      destinatario: email.recipient,
      asunto: email.subject,
      cuerpo: email.body,
    })
    .select("id, incidente_id, destinatario, asunto, cuerpo, estado, creado_en")
    .single();

  if (saveError) {
    console.error("Error guardando email saliente:", saveError);
    return new Response(JSON.stringify({ error: "No se pudo guardar el correo" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify({ email: savedEmail }), {
    status: 201,
    headers: { "Content-Type": "application/json" },
  });
});