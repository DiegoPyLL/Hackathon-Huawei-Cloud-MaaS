# Despliegue

> Actualizado: 31-08-2026

## Artefacto

La aplicación se entrega como un contenedor HTTP sin estado:

```bash
docker build -t maas-decision-brief .
docker run --rm -p 8000:8000 --env-file .env maas-decision-brief
```

`.dockerignore` excluye `.env`, configuración de agentes, pruebas y documentación.
La API key se inyecta en tiempo de ejecución; nunca se copia a la imagen.

## Elección pendiente en Huawei Cloud

El runtime público se elegirá después de comprobar con HuaweiCloud DevKit qué
servicio está disponible en la región y créditos de la hackathon. El requisito es
aceptar una imagen de contenedor, HTTPS, variables secretas y health check
`GET /api/health`. No se atribuye un despliegue a Huawei hasta aprovisionarlo y
pasar el smoke test live.

Antes de publicar el endpoint, el gateway debe limitar tasa y concurrencia. El
servidor incluido no autentica usuarios ni es una frontera de control de costes;
exponerlo directamente con `MAAS_MODE=live` permitiría consumo no autorizado.

## Gate de evidencia

```bash
python3 scripts/prueba-humo.py --url https://URL-DESPLEGADA --require-mode live
```

Guardar junto a la demo: fecha, URL, commit del proyecto, modelo, región y salida
del smoke test. No guardar la API key ni cuerpos completos de conversación.

## Rollback y contingencia

- Rollback: desplegar la imagen anterior; no hay migraciones de datos.
- Proveedor caído: mostrar el error y cambiar manualmente a `mock` si se necesita
  continuar la explicación de UX.
- Credencial expuesta: revocar y rotar antes de volver a desplegar.
