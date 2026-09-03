-- ============================================================
-- Schema: Sistema de tickets/incidentes para Incident Response Agent
-- Entrada: correo de soporte -> parseo -> ticket estructurado
-- Taxonomia canonica de 8 tipos de problema
-- ============================================================

create extension if not exists "pgcrypto";

-- ------------------------------------------------------------
-- Tabla: emails_entrantes
-- Registro crudo de cada correo que llega a la casilla de soporte,
-- antes de cualquier interpretacion. Nunca se borra ni se edita.
-- ------------------------------------------------------------
create table emails_entrantes (
  id uuid primary key default gen_random_uuid(),
  message_id text unique not null,        -- Message-ID del email, evita duplicados
  remitente text not null,
  asunto text not null,
  cuerpo text not null,
  headers jsonb default '{}'::jsonb,       -- headers crudos por si se necesitan despues
  adjuntos jsonb default '[]'::jsonb,      -- referencias a adjuntos (logs, capturas, etc.)

  procesado boolean not null default false,   -- true una vez que se genero (o descarto) un ticket
  incidente_id uuid,                          -- se completa cuando se crea el ticket asociado

  recibido_en timestamptz not null default now(),
  procesado_en timestamptz
);

create index idx_emails_procesado on emails_entrantes (procesado);
create index idx_emails_recibido_en on emails_entrantes (recibido_en desc);

-- ------------------------------------------------------------
-- Tabla principal: incidentes
-- El ticket estructurado que consume el agente
-- ------------------------------------------------------------
create table incidentes (
  id uuid primary key default gen_random_uuid(),
  ticket_numero text unique not null,           -- ej. INC-0042
  titulo text not null,
  descripcion text not null,

  -- Taxonomia canonica: exactamente estos 8 tipos, sin excepcion
  tipo_problema text not null check (tipo_problema in (
    'indisponibilidad',       -- 1. servicio caido, endpoint no responde
    'degradacion',            -- 2. latencia, timeouts, lentitud
    'error_funcional',        -- 3. bug, calculo incorrecto, flujo roto
    'acceso_identidad',       -- 4. login, permisos, MFA, cuenta bloqueada
    'datos',                  -- 5. faltantes, incorrectos, sincronizacion fallida
    'integracion_terceros',   -- 6. API externa, webhook, pasarela de pago
    'capacidad',              -- 7. disco, memoria, cuota, rate limit
    'seguridad'               -- 8. actividad sospechosa, credencial expuesta, phishing
  )),

  severidad text not null check (severidad in ('baja', 'media', 'alta', 'critica')),
  sistema_afectado text not null,               -- ej. payments-service, auth-service

  estado text not null default 'abierto'
    check (estado in ('abierto', 'en_progreso', 'resuelto', 'cerrado')),

  dificultad text not null default 'medio'
    check (dificultad in ('facil', 'medio', 'dificil')),

  canal_origen text not null default 'email'
    check (canal_origen in ('email', 'manual', 'generador_automatico', 'kubernetes_trigger', 'github_webhook')),

  origen_email_id uuid references emails_entrantes(id),  -- null si no vino de un correo

  -- Campos ocultos al agente: usados solo para calificar su desempeno
  causa_raiz_real text,
  solucion_esperada text,

  logs_adjuntos jsonb default '[]'::jsonb,
  metadata jsonb default '{}'::jsonb,

  creado_en timestamptz not null default now(),
  actualizado_en timestamptz not null default now(),
  resuelto_en timestamptz
);

alter table emails_entrantes
  add constraint fk_emails_incidente foreign key (incidente_id) references incidentes(id);

create index idx_incidentes_estado on incidentes (estado);
create index idx_incidentes_tipo_problema on incidentes (tipo_problema);
create index idx_incidentes_creado_en on incidentes (creado_en desc);
create index idx_incidentes_sistema_afectado on incidentes (sistema_afectado);

-- ------------------------------------------------------------
-- Tabla: incidente_eventos
-- Bitacora de lo que hace el agente con cada incidente
-- ------------------------------------------------------------
create table incidente_eventos (
  id uuid primary key default gen_random_uuid(),
  incidente_id uuid not null references incidentes(id) on delete cascade,

  tipo_evento text not null
    check (tipo_evento in (
      'diagnostico',
      'accion_propuesta',
      'accion_ejecutada',
      'escalado_a_humano',
      'comentario',
      'resolucion'
    )),

  contenido text not null,
  confianza numeric(3,2),
  herramienta_usada text,               -- 'github', 'kubernetes', 'postgresql', 'server', etc.
  requiere_aprobacion boolean default false,
  aprobado_por_humano boolean,

  creado_en timestamptz not null default now()
);

create index idx_eventos_incidente_id on incidente_eventos (incidente_id);

-- ------------------------------------------------------------
-- Trigger: actualizar "actualizado_en" automaticamente
-- ------------------------------------------------------------
create or replace function set_actualizado_en()
returns trigger as $$
begin
  new.actualizado_en = now();
  return new;
end;
$$ language plpgsql;

create trigger trg_incidentes_actualizado_en
before update on incidentes
for each row
execute function set_actualizado_en();

-- ------------------------------------------------------------
-- Vista: incidentes_agente
-- Lo que ve el agente. Oculta causa_raiz_real y solucion_esperada.
-- ------------------------------------------------------------
create view incidentes_agente as
select
  id,
  ticket_numero,
  titulo,
  descripcion,
  tipo_problema,
  severidad,
  sistema_afectado,
  estado,
  logs_adjuntos,
  creado_en,
  actualizado_en
from incidentes;

-- ------------------------------------------------------------
-- Vista: taxonomia_resumen
-- Util para dashboards: cuantos incidentes hay por tipo y severidad
-- ------------------------------------------------------------
create view taxonomia_resumen as
select
  tipo_problema,
  severidad,
  count(*) as total,
  count(*) filter (where estado = 'resuelto') as resueltos
from incidentes
group by tipo_problema, severidad
order by tipo_problema, severidad;

-- ------------------------------------------------------------
-- Numeracion automatica de tickets: INC-0001, INC-0002...
-- ------------------------------------------------------------
create sequence if not exists incidentes_numero_seq;

create or replace function generar_ticket_numero()
returns text as $$
begin
  return 'INC-' || lpad(nextval('incidentes_numero_seq')::text, 4, '0');
end;
$$ language plpgsql;

-- Ejemplo de flujo completo: email entra -> se guarda crudo -> se clasifica -> se crea ticket
--
-- 1) insert into emails_entrantes (message_id, remitente, asunto, cuerpo)
--    values ('<abc123@mail>', 'usuario@cliente.com', 'No puedo pagar en checkout', 'Me sale error al pagar...');
--
-- 2) (proceso de clasificacion, manual o con LLM, decide tipo_problema, severidad, etc.)
--
-- 3) insert into incidentes (ticket_numero, titulo, descripcion, tipo_problema, severidad,
--       sistema_afectado, dificultad, canal_origen, origen_email_id, causa_raiz_real, solucion_esperada)
--    values (generar_ticket_numero(), 'Fallo al pagar en checkout',
--       'El usuario reporta error al intentar pagar', 'integracion_terceros', 'alta',
--       'checkout-api', 'medio', 'email', '<uuid del email>',
--       'la pasarela de pago externa esta devolviendo timeout', 'reintentar con backoff o notificar al proveedor');
--
-- 4) update emails_entrantes set procesado = true, procesado_en = now(), incidente_id = '<uuid del incidente>'
--    where id = '<uuid del email>';

-- ------------------------------------------------------------
-- Realtime: notificaciones push al agente cuando llega un ticket nuevo
-- ------------------------------------------------------------
alter publication supabase_realtime add table incidentes;
alter publication supabase_realtime add table incidente_eventos;
alter publication supabase_realtime add table emails_entrantes;

-- ------------------------------------------------------------
-- Row Level Security
-- ------------------------------------------------------------
alter table emails_entrantes enable row level security;
alter table incidentes enable row level security;
alter table incidente_eventos enable row level security;

create policy "service_role_full_access_emails"
  on emails_entrantes for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "service_role_full_access_incidentes"
  on incidentes for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "service_role_full_access_eventos"
  on incidente_eventos for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
