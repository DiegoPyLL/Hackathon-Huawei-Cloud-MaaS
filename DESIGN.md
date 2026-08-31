# {{NOMBRE_PROYECTO}}, Design System

> Plantilla. Reemplazar cada `{{PLACEHOLDER}}` con los valores reales del proyecto y borrar las secciones que no apliquen.
> Las reglas sin placeholder son doctrina y se mantienen tal cual.

## 1. Identidad de marca

**Nombre:** {{NOMBRE_PROYECTO}}

**Concepto:** {{ORIGEN_DEL_NOMBRE_Y_QUE_COMUNICA}}

La marca debe transmitir: {{ATRIBUTO_1}}, {{ATRIBUTO_2}}, {{ATRIBUTO_3}}, {{ATRIBUTO_4}}.

**Lo que la marca no es:** {{MALENTENDIDO_A_EVITAR}}. Definir esto importa tanto como definir lo que sí es.

### Concepto central

> {{TAGLINE}}

---

## 2. Dirección visual

La identidad visual debe combinar: **{{EJE_1}} + {{EJE_2}} + {{EJE_3}}**.

La interfaz debe ser limpia, moderna, clara, profesional, accesible, rápida de comprender y visualmente ordenada.

Evitar:

* Interfaces excesivamente corporativas
* Gradientes exagerados
* Exceso de efectos
* Glassmorphism excesivo
* Sombras demasiado fuertes
* Colores saturados en grandes superficies
* Interfaces que parezcan una herramienta de marketing genérica

---

## 3. Paleta de colores

Cada color de identidad se define con su rol, no solo con su valor. Un color sin regla de uso termina aplicándose en cualquier parte.

### Color principal

**HEX:** `{{HEX_PRINCIPAL}}`

Representa: {{QUE_REPRESENTA}}

Uso: navbar, botones principales, títulos importantes, elementos de navegación.

### Color secundario

**HEX:** `{{HEX_SECUNDARIO}}`

Uso: links, estados activos, botones secundarios, gráficos, elementos interactivos.

No debe dominar toda la interfaz.

### Color de acento

**HEX:** `{{HEX_ACENTO}}`

Uso: {{ELEMENTO_DISTINTIVO_DEL_PRODUCTO}}, badges, highlights, métricas destacadas.

Reservado para lo que distingue al producto. No usarlo como color de todos los botones principales: si está en todas partes, deja de significar algo.

### Colores de estado

| Estado | HEX | Uso |
| --- | --- | --- |
| Éxito | `{{HEX_EXITO}}` | Confirmaciones, métricas positivas, incrementos |
| Advertencia | `{{HEX_ADVERTENCIA}}` | Avisos que no bloquean |
| Error | `{{HEX_ERROR}}` | Errores de validación, fallos, disminuciones |

---

## 4. Colores neutros

| Rol | HEX | Uso |
| --- | --- | --- |
| Background | `{{HEX_BACKGROUND}}` | Fondo principal de la aplicación |
| Surface | `{{HEX_SURFACE}}` | Cards, modales, formularios, paneles |
| Border | `{{HEX_BORDER}}` | Separadores, bordes, inputs |
| Text Primary | `{{HEX_TEXT_PRIMARY}}` | Títulos y texto principal |
| Text Secondary | `{{HEX_TEXT_SECONDARY}}` | Descripciones, información secundaria, labels |
| Text Muted | `{{HEX_TEXT_MUTED}}` | Placeholders, información auxiliar, estados deshabilitados |

---

## 5. Regla 60/30/10

Distribución visual de la interfaz:

* **60 %** neutros y fondo
* **30 %** color principal
* **10 %** acento y estados

El acento se usa de forma estratégica. Una pantalla saturada del color distintivo deja de comunicar lo que ese color significa.

---

## 6. Dark Mode

Soporte obligatorio. Los colores de identidad se mantienen; se ajusta su luminosidad para conservar contraste.

| Rol | HEX |
| --- | --- |
| Dark Background | `{{HEX_DARK_BACKGROUND}}` |
| Dark Surface | `{{HEX_DARK_SURFACE}}` |
| Dark Elevated | `{{HEX_DARK_ELEVATED}}` |
| Dark Border | `{{HEX_DARK_BORDER}}` |
| Dark Text Primary | `{{HEX_DARK_TEXT_PRIMARY}}` |
| Dark Text Secondary | `{{HEX_DARK_TEXT_SECONDARY}}` |

El modo oscuro se implementa con tokens redefinidos, nunca duplicando reglas de color por componente.

---

## 7. Tipografía

**Principal:** {{TIPOGRAFIA}} — por defecto, **Inter**: excelente legibilidad, buena representación numérica y amplio soporte.

La fuente se sirve local y autoalojada, con `font-display: swap` y solo los pesos que se usan. Cada peso adicional es peso de descarga y riesgo de layout shift.

### Pesos

* **400** texto normal
* **500** labels y navegación
* **600** botones y elementos destacados
* **700** títulos
* **800** titulares de landing page

Evitar demasiados pesos dentro de una misma pantalla.

---

## 8. Jerarquía tipográfica

| Nivel | Tamaño | Peso |
| --- | --- | --- |
| H1 | 48–64 px | 700/800 |
| H2 | 32–40 px | 700 |
| H3 | 24–28 px | 600/700 |
| Body | 16 px | 400 |
| Small | 14 px | 400/500 |
| Caption | 12 px | 500 |

H1 se reserva para landing pages. La interfaz prioriza la legibilidad por sobre la densidad.

Los tamaños escalan por breakpoint (XL, L, M, S) sin provocar reflow ni desbordes.

---

## 9. Espaciado, radios y elevación

* **Escala de espaciado:** múltiplos de 4 px. Sin valores arbitrarios.
* **Border radius:** {{RADIO}} px en botones e inputs, {{RADIO_CARD}} px en cards. Un solo criterio en todo el sistema.
* **Sombras:** extremadamente sutiles. Los elementos no deben parecer flotantes.

---

## 10. Logo

Concepto: {{CONCEPTO_DEL_LOGO}}

El símbolo debe funcionar de forma independiente del logotipo y ser legible en favicon, app icon, avatar, redes sociales y material impreso.

Evitar logos excesivamente detallados: lo que no se lee a 16 px no sirve como favicon.

---

## 11. Iconografía

**Lucide Icons** por defecto: stroke uniforme, geometría simple, buena legibilidad.

Los iconos complementan la información, no reemplazan etiquetas importantes. Un icono sin texto solo es aceptable cuando su significado es universal.

Se importan individualmente, nunca la librería completa.

---

## 12. Componentes

### Botones

| Variante | Background | Texto | Borde |
| --- | --- | --- | --- |
| Primary | `{{HEX_PRINCIPAL}}` | `{{HEX_SURFACE}}` | — |
| Secondary | `{{HEX_SURFACE}}` | `{{HEX_PRINCIPAL}}` | `{{HEX_BORDER}}` |
| Ghost | transparente | `{{HEX_PRINCIPAL}}` | — |

Todos los estados están definidos: reposo, hover, activo, foco visible y deshabilitado. El foco visible nunca se elimina.

### Cards

Fondo `{{HEX_SURFACE}}`, borde `{{HEX_BORDER}}`, radio {{RADIO_CARD}} px, sombra sutil.

### Formularios

Todo input tiene label asociado. Los errores se comunican con texto, no solo con color.

---

## 13. Visualización de datos

El color debe tener significado. No usar múltiples colores arbitrarios.

| Color | Significado |
| --- | --- |
| Principal / secundario | {{SIGNIFICADO}} |
| Acento | {{SIGNIFICADO}} |
| Éxito | Crecimiento, resultados positivos |
| Error | Problemas, disminuciones |
| Gris | Información secundaria |

El usuario debe entender el estado en menos de 10 segundos. Mostrar primero los datos que permiten tomar decisiones, no todos los datos disponibles.

---

## 14. Movimiento

Las animaciones deben comunicar información, no decorar.

* **Duración:** 150–300 ms; hasta 500 ms en transiciones importantes.
* Animar solo `transform` y `opacity`: son las propiedades que no fuerzan reflow.
* Respetar `prefers-reduced-motion`.
* Ninguna animación puede provocar layout shift.

---

## 15. Imágenes e ilustraciones

{{QUE_DEBEN_REPRESENTAR_LAS_IMAGENES}}

Evitar fotografía corporativa genérica de banco de imágenes. Las ilustraciones son minimalistas y coherentes con la paleta.

**Requisitos técnicos, sin excepción:** formatos modernos (AVIF/WebP), dimensiones explícitas para evitar CLS, `loading="lazy"` salvo en el LCP, y texto alternativo descriptivo.

---

## 16. Voz y contenido

Principio: **el producto debe ser más fácil de usar que de explicar.**

* Evitar lenguaje técnico y configuraciones innecesarias.
* Explicar las métricas en lugar de asumir que se entienden.
* Mostrar recomendaciones accionables.
* Reducir la cantidad de pasos.

Preferir el lenguaje del usuario al del sistema: no «Conversion Rate», sino «{{EQUIVALENTE_EN_LENGUAJE_DEL_USUARIO}}».

---

## 17. Landing page

La landing vende el resultado, no las funcionalidades.

El hero comunica de inmediato **qué es**, **para quién es** y **qué resultado produce**, con un CTA principal y uno secundario.

Estructura recomendada: Hero · Problema · Cómo funciona · {{SECCIONES_DE_VALOR}} · Resultados · CTA.

---

## 18. Accesibilidad

Requisito, no mejora opcional. El objetivo es 100 en Lighthouse Accessibility.

* Contraste mínimo AA: 4.5:1 en texto normal, 3:1 en texto grande y elementos de interfaz.
* El color nunca es el único portador de significado.
* Todo elemento interactivo es alcanzable por teclado y tiene foco visible.
* Jerarquía de encabezados correcta y sin saltos.
* Objetivos táctiles de al menos 44 × 44 px.

---

## 19. Personalidad visual

**Debe sentirse:** {{ADJETIVO_1}}, {{ADJETIVO_2}}, {{ADJETIVO_3}}.

**No debe sentirse:** infantil, corporativo, excesivamente técnico, agresivo, barato, genérico.

---

## 20. Principio rector

Toda decisión de diseño responde una pregunta:

> ¿Esto ayuda a {{USUARIO}} a {{OBJETIVO_DEL_USUARIO}}?

Si la respuesta es no, probablemente el elemento no necesita existir.

---

## 21. Resumen de identidad

| Campo | Valor |
| --- | --- |
| Marca | {{NOMBRE_PROYECTO}} |
| Categoría | {{CATEGORIA}} |
| Promesa | {{PROMESA}} |
| Personalidad | {{PERSONALIDAD}} |
| Color principal | `{{HEX_PRINCIPAL}}` |
| Color de acción | `{{HEX_SECUNDARIO}}` |
| Color distintivo | `{{HEX_ACENTO}}` |
| Tipografía | {{TIPOGRAFIA}} |
| Iconografía | Lucide |
| Tagline | {{TAGLINE}} |
