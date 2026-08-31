# Volutus, Principios de Desarrollo

## Objetivo

> Rellenar al iniciar el proyecto. Todo lo demás en este archivo es doctrina fija y no debe editarse por proyecto.

Desarrollar **MaaS Decision Brief**: convertir un reto ambiguo en un brief
accionable mediante un vertical slice demostrable sobre Huawei Cloud MaaS.

- **Usuarios:** equipos que presentan una solución GenAI y jurados que necesitan
  comprender su valor y evidencia en pocos minutos.
- **Dominio:** prototipado y soporte a decisiones con modelos generativos.
- **Diferenciador:** modo real o simulado siempre visible, streaming, métricas y
  evaluación repetible desde el primer vertical slice.

Debes priorizar: rendimiento, calidad técnica, diseño y posicionamiento en buscadores.

Toda decisión de desarrollo debe justificarse en función de estos principios.

---

# Filosofía

La implementación debe seguir tres pilares fundamentales, en este orden:

1. **Simpleza del código**

   - Escribir el código más simple posible.
   - Evitar complejidad innecesaria.
   - Favorecer la legibilidad sobre la "inteligencia" del código.
   - No introducir abstracciones prematuras.
2. **Destreza técnica**

   - Aplicar buenas prácticas de ingeniería.
   - Mantener una arquitectura limpia.
   - Priorizar mantenibilidad y escalabilidad.
   - Evitar duplicación de código (DRY).
   - Mantener componentes pequeños y reutilizables cuando aporte valor.
3. **Buen gusto en el diseño**

   - Diseño moderno, limpio y profesional.
   - Excelente jerarquía visual.
   - Espacios consistentes.
   - Animaciones discretas y con propósito.
   - La estética nunca debe perjudicar el rendimiento.

---

# Prioridades Absolutas

Estas prioridades tienen precedencia sobre cualquier otra decisión.

## 1. SEO

El objetivo principal es alcanzar el máximo rendimiento posible en SEO.

La implementación debe aspirar a obtener en Google Lighthouse.:

- 100 Performance
- 100 Accessibility
- 100 Best Practices
- 100 SEO
- 3/3 Agentic Search

Cada cambio debe evaluarse considerando su impacto sobre estas métricas.

---

## 2. Rendimiento

Todo el sitio debe estar optimizado.

Priorizar:

- Tiempo de carga mínimo.
- JavaScript reducido al mínimo.
- CSS optimizado.
- Imágenes optimizadas.
- Lazy Loading cuando corresponda.
- Evitar dependencias innecesarias.
- Reducir el tamaño del bundle.
- Optimizar el Critical Rendering Path.
- Evitar re-renderizados innecesarios.
- Mantener un excelente Core Web Vitals.

---

## 3. Simplicidad

Antes de agregar cualquier solución, preguntarse:

> ¿Existe una forma más simple de resolver este problema?

Si la respuesta es sí, utilizarla.

---

## 4. Seguridad

Todo el sitio debe seguir buenas prácticas de seguridad.

Considerar:

- Sanitización de entradas.
- Evitar exposición de información sensible.
- Uso correcto de variables de entorno.
- Headers de seguridad cuando corresponda.
- Dependencias actualizadas.
- Evitar código inseguro.

---

## 5. Responsive Design

La experiencia debe ser excelente en cualquier dispositivo.

Diseñar para los siguientes breakpoints:

- XL
- L
- M
- S

No deben existir problemas de:

- Overflow.
- Layout Shift.
- Escalado incorrecto.
- Contenido inaccesible.

---

# Optimización del Código

Siempre:

- Eliminar código muerto.
- Eliminar imports sin uso.
- Eliminar componentes sin uso.
- Eliminar estilos sin uso.
- Eliminar dependencias innecesarias.
- Reducir duplicación.
- Mantener archivos pequeños cuando sea razonable.

Nunca dejar código comentado como respaldo.

El historial de Git cumple esa función.

---

# Uso de Recursos

Ser eficiente con el uso de recursos.

- Realizar únicamente el trabajo necesario.
- Evitar modificaciones irrelevantes.
- Evitar reescrituras completas si no aportan valor.
- Minimizar el consumo de créditos y contexto.
- Priorizar cambios pequeños y precisos.

---

# Fuente de Información

Antes de asumir información, consultar en este orden:

1. **`docs/`** de este repositorio — fuente de verdad del proyecto. Ver `docs/README.md` para la organización.
2. **Skills en `.claude/skills/`** — biblioteca de conocimiento técnico (seguridad, backend, SEO, mobile). Ante una duda de dominio, invocar la skill correspondiente antes de improvisar.
3. **Vault de Obsidian** en `{{RUTA_VAULT}}` — notas personales y contexto de negocio.

---

# Organización del Repositorio

- La documentación vive en `docs/`, nunca suelta en la raíz. Las reglas de categorización están en `docs/README.md` y deben respetarse al crear cualquier documento nuevo.
- Las decisiones técnicas con consecuencias se registran como ADR en `docs/architecture/decisions/`.
- `.claude/skills/` es un submódulo git (repositorio `FullSkills`). No editar su contenido desde este proyecto: los cambios se hacen en el repositorio de skills.
- La configuración compartida de Claude va en `.claude/settings.json`; la personal en `.claude/settings.local.json`, que no se versiona.

---

# Estándares de Calidad

Todo el código generado debe cumplir con:

- Código limpio.
- Alta legibilidad.
- Nombres descriptivos.
- Responsabilidad única.
- Consistencia de estilo.
- Bajo acoplamiento.
- Alta cohesión.
- Sin warnings.
- Sin errores del linter.
- Sin errores de TypeScript.
- Sin deuda técnica evitable.
- Énfasis en la seguridad del sitio y sus componentes

---

# Criterios para Aceptar un Cambio

Antes de considerar una tarea terminada, verificar:

- El código es más simple que antes.
- No existe código muerto.
- No se degradó el rendimiento.
- No se degradó el SEO.
- No se degradó la accesibilidad.
- No se degradó la seguridad.
- Funciona correctamente en XL, L, M y S.
- No introduce complejidad innecesaria.
- Mantiene la consistencia visual del proyecto.
- Cumple las buenas prácticas de desarrollo.

Si cualquiera de estos puntos falla, el trabajo no debe considerarse terminado.
