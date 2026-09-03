# Documentación

Fuente de verdad del proyecto. Si una decisión no está aquí, no está tomada.

## Mapa

| Carpeta | Responde a | Ejemplos |
| --- | --- | --- |
| [`product/`](product/) | Qué construimos y para quién | visión, alcance, usuarios, contenido |
| _(pendiente)_ `design/` | Cómo se ve y se siente | design system, identidad, accesibilidad |
| [`architecture/`](architecture/) | Cómo está construido y por qué | stack, estructura, modelo de datos, ADRs |
| [`development/`](development/) | Cómo se trabaja en él | entorno, convenciones, testing, flujo git |
| _(pendiente)_ `performance-seo/` | Cómo se mide la calidad | presupuesto de rendimiento, checklist SEO, Core Web Vitals |
| [`operations/`](operations/) | Cómo vive en producción | despliegue, entornos, seguridad, incidentes |
| [`assets/`](assets/) | Imágenes de la documentación | diagramas, capturas |

## Reglas de organización

1. **Nada suelto en la raíz de `docs/`.** El único archivo permitido aquí es este `README.md`. Todo documento pertenece a una categoría.
2. **Un documento, un lugar.** Si encaja en dos categorías, decide por el lector: quien lo busca, ¿qué pregunta se está haciendo? Esa es la carpeta. No duplicar; enlazar.
3. **Máximo dos niveles** dentro de una categoría. Si necesitas un tercero, la categoría está mal planteada o el documento debería dividirse.
4. **Nombres en kebab-case, sin acentos ni ñ**, descriptivos y en español: `modelo-de-datos.md`, `checklist-seo.md`. Nunca `doc1.md` ni `notas.md`.
5. **Cada carpeta mantiene su `README.md`** con una línea por documento. Si añades un documento, añades su línea.
6. **Las decisiones técnicas van a `architecture/decisions/`** como ADR numerado, no dispersas en otros documentos.
7. **Lo que caduca lleva fecha.** Benchmarks, auditorías y snapshots empiezan con `> Actualizado: DD-MM-AAAA`. Sin fecha, se asume vigente y eso miente.
8. **Las imágenes van a `assets/<categoria>/`**, referenciadas con rutas relativas. Nunca imágenes junto al documento.
9. **Un documento que ya no es verdad se borra o se corrige**, no se deja "por si acaso". El historial de git cumple esa función.

## Al empezar un proyecto nuevo

1. Completar `product/vision.md` y el bloque `Objetivo` de [`.claude/CLAUDE.md`](../.claude/CLAUDE.md).
2. Rellenar `design/design-system.md` con la identidad real.
3. Registrar el stack elegido como primer ADR en `architecture/decisions/`.
4. Borrar los documentos plantilla que el proyecto no vaya a usar.
