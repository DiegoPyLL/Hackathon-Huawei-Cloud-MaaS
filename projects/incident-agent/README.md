# Incident Response Agent — Sistema de tickets

Proyecto: agente de IA que diagnostica y responde a incidentes, alimentado por un
sistema de tickets que se genera a partir de correos de soporte.

## Arquitectura general

```
Correo a soporte.jsonch@gmail.com
        |
        v
   Gmail (reenvio automatico)
        |
        v
Postmark Inbound Stream (Server: "My First Server")
        |
        v (webhook)
Supabase Edge Function: recibir-email
        |
        v
Tabla emails_entrantes (Supabase)
        |
        v (clasificacion, pendiente de definir)
Tabla incidentes (ticket estructurado)
        |
        v
Incident Response Agent (LLM + herramientas: GitHub, GitLab,
Kubernetes, PostgreSQL, Supabase DB, Server via SSH)
```

## Taxonomia canonica de problemas (8 tipos, fijos)

1. `indisponibilidad` — servicio caido, endpoint no responde
2. `degradacion` — latencia, timeouts, lentitud
3. `error_funcional` — bug, calculo incorrecto, flujo roto
4. `acceso_identidad` — login, permisos, MFA, cuenta bloqueada
5. `datos` — faltantes, incorrectos, sincronizacion fallida
6. `integracion_terceros` — API externa, webhook, pasarela de pago
7. `capacidad` — disco, memoria, cuota, rate limit
8. `seguridad` — actividad sospechosa, credencial expuesta, phishing

Esta taxonomia esta forzada a nivel de base de datos con un `check constraint`
en la columna `tipo_problema` de la tabla `incidentes` (ver `schema/schema_incidentes.sql`).

## Estructura del proyecto

```
incident-agent/
├── README.md                              <- este archivo
├── schema/
│   └── schema_incidentes.sql              <- schema completo de Supabase
└── supabase/
    ├── config.toml                        <- config minima de la CLI
    └── functions/
        └── recibir-email/
            └── index.ts                   <- Edge Function que recibe el webhook de Postmark
                └── generar-email/
                        └── index.ts                   <- Genera y guarda borradores de respuesta
```

## Estado actual (lo ya hecho)

- [x] Postmark: servidor "My First Server" creado, "Default Inbound Stream" activo
- [x] Gmail (soporte.jsonch@gmail.com): reenvio automatico configurado hacia la
      direccion inbound de Postmark, confirmado y probado con un correo real
- [x] Supabase: proyecto creado (`kuroishi-py's Project`, region us-east-2)
- [x] Supabase CLI instalada via Scoop, login hecho
- [x] Schema de base de datos definido (`schema/schema_incidentes.sql`)
- [x] Codigo de la Edge Function `recibir-email` escrito
- [x] Generacion de borradores de correo a partir de un incidente
- [ ] Proyecto vinculado con `supabase link` (project-ref: `vrdkupzjrgtlgiexhpie`)
- [ ] Secrets configurados (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`)
- [ ] Edge Function desplegada
- [ ] URL de la funcion pegada en el Webhook URL del Inbound Stream de Postmark
- [ ] Prueba de punta a punta (correo -> Gmail -> Postmark -> Supabase)
- [ ] Logica de clasificacion automatica (tipo_problema, severidad) desde el texto del correo
- [ ] Diseño del Incident Response Agent en si (motor de razonamiento + herramientas)

### Generar un correo

La función `generar-email` crea un borrador en `emails_salientes`. Usa como
destinatario el remitente del correo de origen del incidente, aunque se puede
indicar otro destinatario explícitamente.

```powershell
$body = @{ incidente_id = "<uuid-del-incidente>" } | ConvertTo-Json
Invoke-RestMethod `
        -Method Post `
        -Uri "https://<project-ref>.supabase.co/functions/v1/generar-email" `
        -Headers @{ Authorization = "Bearer <service-role-key>" } `
        -ContentType "application/json" `
        -Body $body
```

La respuesta contiene `id`, `destinatario`, `asunto`, `cuerpo` y `estado` del
borrador. La función no envía el correo: un proceso de salida podrá tomar los
registros con estado `borrador`, entregarlos al proveedor y actualizar
`estado`, `proveedor_id` y `enviado_en`.

## Como continuar (pasos pendientes)

### 1. Aplicar el schema en Supabase

En el dashboard de Supabase, entra a **SQL Editor** y pega el contenido completo de
`schema/schema_incidentes.sql`, luego ejecuta. Esto crea las tablas
`emails_entrantes`, `incidentes`, `incidente_eventos`, las vistas y los triggers.

### 2. Vincular el proyecto local

Desde la carpeta `incident-agent/`, en la terminal:

```powershell
supabase link --project-ref vrdkupzjrgtlgiexhpie
```

Te pedira la contrasena de la base de datos que definiste al crear el proyecto.

### 3. Configurar los secrets de la funcion

```powershell
supabase secrets set SUPABASE_URL=https://vrdkupzjrgtlgiexhpie.supabase.co
supabase secrets set SUPABASE_SERVICE_ROLE_KEY=<tu-service-role-key>
```

La `service_role key` esta en el dashboard de Supabase: **Settings > API > service_role**.
Nunca subas este valor a un repositorio publico.

### 4. Desplegar la Edge Function

```powershell
supabase functions deploy recibir-email --no-verify-jwt
```

Esto te devuelve una URL publica del tipo:
`https://vrdkupzjrgtlgiexhpie.supabase.co/functions/v1/recibir-email`

### 5. Conectar el webhook en Postmark

En Postmark: **My First Server > Default Inbound Stream > Settings**, pega esa URL
en el campo de Webhook URL y guarda.

### 6. Probar de punta a punta

Envia un correo de prueba a `soporte.jsonch@gmail.com` y confirma que:
- Aparece en el Activity de Postmark sin el error de "No inbound hook URL"
- Aparece una fila nueva en la tabla `emails_entrantes` de Supabase

## Datos de referencia del proyecto

- Correo de soporte: `soporte.jsonch@gmail.com`
- Direccion inbound de Postmark: `d66b0ba2b2b829008fc4b8fc470d9c3d@inbound.postmarkapp.com`
- Supabase project-ref: `vrdkupzjrgtlgiexhpie`
- Supabase URL: `https://vrdkupzjrgtlgiexhpie.supabase.co`

## Herramientas disponibles para el agente (fase posterior)

- GitHub / GitLab — pipelines, PRs, commits, archivos del repo
- Kubernetes — pods, eventos, logs, uso de recursos del cluster
- PostgreSQL / Supabase Database — esquemas, tablas, consultas SELECT
- Server (SSH) — estado, uso de disco y servicios de un host
