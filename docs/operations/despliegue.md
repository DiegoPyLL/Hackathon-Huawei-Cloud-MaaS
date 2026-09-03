# Despliegue

> Actualizado: 03-09-2026

## Artefacto

La aplicación se entrega como un contenedor HTTP sin estado:

```bash
docker build -t maas-decision-brief .
docker run --rm -p 8080:8080 --env-file .env maas-decision-brief
```

`.dockerignore` excluye `.env`, configuración de agentes, pruebas y documentación.
Las claves —la de Kostra y la `service_role` de Supabase— se inyectan en tiempo
de ejecución; nunca se copian a la imagen.

El contenedor ya no es del todo sin estado: la cola de aprobación vive en
Supabase. Reiniciarlo no pierde aprobaciones pendientes, pero sí exige que las
credenciales del almacén estén presentes.

## Elección pendiente en Huawei Cloud

El runtime público se elegirá después de comprobar con HuaweiCloud DevKit qué
servicio está disponible en la región y créditos de la hackathon. El requisito es
aceptar una imagen de contenedor, HTTPS, variables secretas y health check
`GET /api/health`. No se atribuye un despliegue a Huawei hasta aprovisionarlo y
pasar el smoke test live.

Antes de publicar el endpoint, el gateway debe limitar tasa y concurrencia. El
servidor incluido no autentica usuarios ni es una frontera de control de costes;
exponerlo directamente con `MAAS_MODE=live` permitiría consumo no autorizado.

Con el flujo multiagente esto pesa más que antes: una corrida son hasta ocho
llamadas al modelo, no una. Y las rutas de aprobación (`POST
/api/aprobaciones/{id}`) escriben en la base de datos sin autenticar a quien
decide — la demo asume un único operador en `127.0.0.1`. Publicar ese endpoint
sin una capa de autenticación delante entrega la compuerta de aprobación a
cualquiera.

## Gate de evidencia

```bash
python3 scripts/ejecutablesBase/prueba-humo.py --url https://URL-DESPLEGADA --require-mode live
```

Guardar junto a la demo: fecha, URL, commit del proyecto, **proveedor y modelo de
cada rol** y salida del smoke test. No guardar las claves ni cuerpos completos de
conversación.

## Comprobaciones antes de cada demostración

Dos dependencias externas pueden dejar la demo muerta sin previo aviso:

1. **Saldo de Kostra.** Es prepago y **compartido con la cuenta del chat web**:
   alguien usando el chat consume el mismo saldo. Un `402` a mitad de una corrida
   aborta la corrida entera. Verificar saldo antes de presentar.
2. **Proyecto de Supabase activo.** El free tier pausa proyectos inactivos. Un
   proyecto pausado deja la cola de aprobación sin almacén; la interfaz lo dirá
   con todas sus letras, pero no habrá compuerta que demostrar.

## Rollback y contingencia

- Rollback: desplegar la imagen anterior. El esquema de Supabase sí evoluciona:
  una migración que quite columnas exige revisar si la imagen anterior sigue
  funcionando contra el esquema nuevo.
- Proveedor caído o sin saldo: mostrar el error tal cual —incluido el código y qué
  significa— y cambiar manualmente a `mock` si se necesita continuar la
  explicación de UX, diciéndolo en voz alta.
- Supabase caído: la cola de aprobación se muestra deshabilitada y se explica por
  qué. No se simula una aprobación guardada.
- Credencial expuesta: revocar y rotar antes de volver a desplegar.
