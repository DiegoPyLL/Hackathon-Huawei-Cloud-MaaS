-- Tablas operativas del flujo multiagente descrito en docs/architecture/modelo-de-datos.md.
-- Aplicar solo con autorización explícita sobre el proyecto Supabase.
create table if not exists corridas (
  id uuid primary key, canal text not null, modo_inferencia text not null check (modo_inferencia in ('mock','live')),
  modelos jsonb not null default '{}'::jsonb, llamadas integer not null default 0,
  usage jsonb not null default '{}'::jsonb, estado text not null, diferidos jsonb not null default '[]'::jsonb,
  duracion_ms integer not null default 0, creada_en timestamptz not null default now()
);
create table if not exists incidentes_agente (
  id uuid primary key default gen_random_uuid(), corrida_id uuid not null references corridas(id) on delete cascade,
  incidente_id text not null, titulo text not null, tipo text not null, canal text not null, severidad text not null,
  ataque_activo boolean not null, evidencia jsonb not null, especialistas jsonb not null, motivo_ruteo text not null,
  desviacion_ruteo boolean not null default false, unique(corrida_id, incidente_id)
);
create table if not exists hallazgos (
  id uuid primary key default gen_random_uuid(), corrida_id uuid not null references corridas(id) on delete cascade,
  incidente_id text not null, especialista text not null, estado text not null, causa_raiz text,
  confianza text, evidencia jsonb not null default '[]'::jsonb, descartado jsonb not null default '[]'::jsonb,
  viabilidad text, error text
);
create table if not exists trazas (
  id uuid primary key default gen_random_uuid(), corrida_id uuid not null references corridas(id) on delete cascade,
  fase text not null, origen text not null, detalle text not null default '', ms integer not null,
  estado text not null, iniciada_en timestamptz not null default now()
);
create table if not exists aprobaciones (
  id uuid primary key, corrida_id uuid not null references corridas(id) on delete cascade,
  hallazgo_id text not null, action_id text not null, params jsonb not null,
  riesgo text not null, estado text not null, actor text, nota text,
  creada_en timestamptz not null default now(), decidida_en timestamptz
);
alter table corridas enable row level security;
alter table incidentes_agente enable row level security;
alter table hallazgos enable row level security;
alter table trazas enable row level security;
alter table aprobaciones enable row level security;
