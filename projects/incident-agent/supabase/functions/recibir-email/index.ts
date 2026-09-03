// Edge Function: recibir-email
// Recibe el webhook de Postmark Inbound Stream y guarda el correo
// crudo en la tabla emails_entrantes de Supabase.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(supabaseUrl, supabaseServiceKey);

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "payload invalido, no es JSON" }), {
      status: 400,
    });
  }

  // Postmark manda estos campos en el body del webhook inbound.
  // Referencia: https://postmarkapp.com/developer/webhooks/inbound-webhook
  const messageId = payload.MessageID;
  const remitente = payload.FromFull?.Email ?? payload.From ?? "desconocido";
  const asunto = payload.Subject ?? "(sin asunto)";
  const cuerpo = payload.TextBody ?? payload.HtmlBody ?? "";
  const headers = payload.Headers ?? [];
  const adjuntos = (payload.Attachments ?? []).map((a: any) => ({
    nombre: a.Name,
    tipo: a.ContentType,
    tamano: a.ContentLength,
  }));

  if (!messageId) {
    return new Response(JSON.stringify({ error: "payload sin MessageID" }), {
      status: 400,
    });
  }

  const { error } = await supabase.from("emails_entrantes").insert({
    message_id: messageId,
    remitente,
    asunto,
    cuerpo,
    headers,
    adjuntos,
  });

  if (error) {
    // message_id repetido = Postmark reintentando un correo ya guardado.
    // No es un error real, respondemos 200 para que deje de reintentar.
    if (error.code === "23505") {
      return new Response(JSON.stringify({ status: "duplicado, ignorado" }), {
        status: 200,
      });
    }
    console.error("Error insertando email:", error);
    return new Response(JSON.stringify({ error: error.message }), { status: 500 });
  }

  return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
});
