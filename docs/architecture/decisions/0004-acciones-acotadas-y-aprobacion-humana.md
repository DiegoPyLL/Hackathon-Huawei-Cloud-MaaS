# 0004 — Catálogo cerrado de acciones y aprobación humana

> Estado: Aceptada · Fecha: 03-09-2026

## Contexto

`AGENTS.md`, `vision.md` y `deteccion-incidentes.md` repiten la misma regla: el
agente **propone** una acción correctiva, nunca afirma haberla ejecutado, y una
acción con permisos riesgosos requiere autorización humana explícita.

Hasta ahora esa regla vivía **solo dentro del prompt**. Es decir: la garantía de
que nada se ejecuta sin permiso era que el modelo redactara bien. Mientras el
agente no tuvo forma de tocar nada, la distinción era teórica. Con un almacén real
detrás ([0005](0005-supabase-como-almacen.md)) deja de serlo.

El problema concreto: si un especialista puede proponer una corrección que el
sistema ejecutará, ¿en qué formato la propone? La opción evidente —que emita el SQL—
abre dos agujeros a la vez. El primero es inyección SQL con el modelo de vector. El
segundo es peor: los logs que el agente analiza son texto no confiable escrito por
cualquiera, y `deteccion-incidentes.md` ya reconoce el correo de soporte como el
canal "más propenso a instrucciones hostiles embebidas". Un atacante que consigue
que su texto llegue al agente estaría escribiendo SQL contra la base de datos de
la empresa.

## Decisión

Se decidió que **el modelo nunca emite SQL ni ninguna otra forma de comando
ejecutable**. Un especialista solo puede elegir un `action_id` de un catálogo
cerrado definido en el servidor y rellenar parámetros tipados. El servidor mapea
ese `action_id` a una operación predefinida y parametrizada. Un `action_id` fuera
del catálogo, o parámetros que no pasan su validador, se rechazan como error del
contrato y no se muestran como acción válida.

El catálogo completo, con sus parámetros y validadores, está en
[`contratos-agentes.md`](../contratos-agentes.md).

Dos reglas que se derivan y que también se decidieron aquí:

**El nivel de riesgo y la exigencia de aprobación no los declara el modelo.** Salen
del catálogo del servidor, indexados por `action_id`. Dejar que el modelo etiquete
su propia acción como "de bajo riesgo" sería reintroducir por la puerta de atrás
exactamente lo que este ADR cierra.

**Toda acción marcada como que requiere aprobación se materializa como una fila en
estado `pendiente` y no se ejecuta.** Un humano aprueba o rechaza desde el
dashboard; solo entonces el servidor ejecuta la operación predefinida y registra
actor, timestamp y efecto. Las acciones de riesgo bajo que no requieren aprobación
quedan igualmente registradas en la bitácora con la corrida que las originó.

Con esto, "nunca ejecutada sin autorización explícita" deja de ser una regla de
redacción y pasa a ser un mecanismo: no existe ninguna ruta de código por la que
la salida del modelo alcance la base de datos sin pasar por el catálogo y, cuando
corresponde, por una decisión humana.

## Alternativas descartadas

| Alternativa | Por qué se descartó |
| --- | --- |
| Que el modelo emita SQL y un humano lo revise antes de ejecutar | Convierte al revisor en el único control; un revisor cansado aprueba. Y no cierra la inyección: el SQL hostil ya vendría escrito desde los logs |
| Usar el campo `tools` nativo de Kostra | Traslada la validación al proveedor, fuera de nuestro control, y el `action_id` seguiría siendo texto del modelo. La validación tiene que ocurrir donde está la base de datos |
| SQL del modelo restringido por una lista de tablas o verbos permitidos | Es filtrado de una superficie infinita; siempre queda una forma de escribir lo mismo de otra manera |
| Ejecutar sin aprobación las acciones de riesgo bajo | Difumina la línea justo donde importa que sea nítida, y el nivel de riesgo lo asigna un catálogo que puede equivocarse |
| Que el modelo declare el riesgo de su propia acción | Es pedirle al mismo componente no confiable que se autorice a sí mismo |
| No ejecutar nunca nada y dejar la propuesta en texto | Es el estado actual; no demuestra la compuerta de aprobación, que es justamente lo que hay que demostrar |

## Consecuencias

**A favor:** la salida del modelo deja de ser código y pasa a ser un dato validable
contra un esquema cerrado. La inyección de prompt embebida en los logs pierde su
objetivo más valioso. Y la doctrina de autorización humana queda demostrable ante
un jurado en vez de prometida en un prompt.

**En contra:** el agente solo puede proponer lo que el catálogo contempla. Una
corrección legítima que no esté en la lista no puede proponerse como acción, solo
describirse en texto. Ampliar el catálogo es trabajo manual y deliberado, y así
debe seguir siendo: la fricción es la característica, no el defecto.

**Coste de revertir:** alto en lo conceptual, bajo en lo mecánico. Quitar el
catálogo es fácil; hacerlo devolvería al proyecto a no poder afirmar que ninguna
acción se ejecuta sin autorización, que es una de las promesas centrales.
