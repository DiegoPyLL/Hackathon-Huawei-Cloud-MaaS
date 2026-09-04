# 0009 — Salida de la corrida programada como alerta de code scanning

> Estado: Aceptada · Fecha: 03-09-2026

## Contexto

El [ADR-0006](0006-ejecucion-programada-y-manual.md) decidió que la corrida
programada subiera el reporte como *artifact* del workflow. Un artifact es un
`.zip` que caduca a los 90 días, que nadie mira si no entra al run concreto y
que no distingue un hallazgo crítico de uno menor. Para un agente cuyo producto
son hallazgos de seguridad con severidad, es el sitio equivocado: el resultado
de la corrida nocturna queda enterrado.

Lo que se necesitaba: que cada hallazgo con su severidad, su causa raíz y su
evidencia apareciera como una entrada persistente y clasificada, que se pudiera
abrir, comentar y cerrar, y que el mismo hallazgo repetido noche tras noche no
generara una entrada nueva cada vez.

El repositorio es público, de modo que **code scanning está disponible sin
coste** — en uno privado exigiría GitHub Advanced Security, y esta decisión
habría sido otra.

## Decisión

La corrida programada emite sus hallazgos en **SARIF 2.1.0** y los publica en la
pestaña **Security** del repositorio con `github/codeql-action/upload-sarif`,
bajo la categoría `incident-agent`.

El emisor vive en [`src/maas_demo/sarif.py`](../../../src/maas_demo/sarif.py) y
no conoce GitHub ni HTTP: traduce el resultado del `Orchestrator` a un
documento, y el workflow lo sube. Tres reglas lo gobiernan:

- **El catálogo de reglas son los 8 tipos canónicos**, importados de
  `orchestrator.TYPES`. La taxonomía sigue viviendo en un solo sitio.
- **Un resultado por hallazgo, no por incidente.** El hallazgo es el que trae
  causa raíz, confianza y evidencia; el incidente solo clasifica.
- **Cada resultado lleva `partialFingerprints`** con `<origen>/<especialista>`.
  Es lo que hace que un cron diario mantenga abierta la misma alerta en vez de
  abrir una nueva cada noche.

La severidad del incidente decide `level` (`error`/`warning`/`note`) y
`security-severity` (9.0/7.0/5.0/3.0), que es el número con el que GitHub
clasifica la alerta en Critical/High/Medium/Low.

## Alternativas descartadas

| Alternativa | Por qué se descartó |
| --- | --- |
| Repository Security Advisory (GHSA) real, vía la API de advisories | Los advisories describen vulnerabilidades del código que el repositorio distribuye, no reportes operativos nocturnos. Publicar uno notifica a consumidores aguas abajo y ensucia la base GHSA con incidentes que no son vulnerabilidades de este código |
| Un issue de GitHub por corrida | Legible, pero genera un issue por noche y no clasifica por severidad. Sin deduplicación, el mismo hallazgo reaparece indefinidamente |
| Seguir solo con artifact y resumen del job | Es lo que ya había y es justo el problema: caduca, no clasifica y nadie lo mira |
| Un panel propio publicado en internet | El ADR-0006 ya lo descartó: una URL pública rompe el supuesto de operador único y expone la compuerta de aprobación |

## Consecuencias

**A favor:** los hallazgos quedan donde se buscan hallazgos de seguridad, con
severidad y evidencia, y sobreviven a la caducidad del artifact. La
deduplicación por huella convierte el cron diario en un estado vivo —una alerta
abierta significa que el problema sigue— en vez de un flujo de ruido. El SARIF
se escribe también en local con `--sarif`, así que se inspecciona antes de
publicarlo.

**En contra:** una alerta de code scanning insinúa una vulnerabilidad *en el
código del repositorio*, y aquí describe un incidente operativo de un sistema
observado. La categoría `incident-agent` y el nombre de la herramienta lo
declaran, pero la ambigüedad existe y hay que tenerla presente al leer la
pestaña. Además las alertas apuntan a
`evals/results/incidentes-supabase.jsonl`, un archivo que la corrida genera y
que no está versionado: GitHub muestra la ruta pero no un fragmento de código.

**Coste de revertir:** bajo. Quitar el paso `upload-sarif` deja el SARIF como un
archivo más dentro del artifact, sin tocar el emisor ni el flujo.

## Fuentes volátiles

- Code scanning es gratuito en repositorios **públicos**; en privados requiere
  GitHub Advanced Security. Verificar antes de cambiar la visibilidad del repo.
- GitHub cierra automáticamente las alertas que dejan de aparecer en un SARIF
  posterior de la misma categoría. Con la lectura completa de Supabase cada
  noche eso es lo deseado: si el incidente ya no está, la alerta se cierra sola.

Fuentes: [uploading-a-sarif-file-to-github](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/uploading-a-sarif-file-to-github) · [sarif-support-for-code-scanning](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning) — consultadas el 03-09-2026.
