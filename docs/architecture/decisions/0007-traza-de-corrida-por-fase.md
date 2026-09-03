# 0007 — Traza de corrida por fase

> Estado: Aceptada · Fecha: 03-09-2026

## Contexto

La corrida ahora depende de dos servicios externos: Kostra para inferencia
([ADR-0002](0002-proveedor-de-inferencia-kostra.md)) y Supabase para almacén
([ADR-0005](0005-supabase-como-almacen.md)). `corridas` ya guarda `llamadas` y
`usage`, pero ningún tiempo. Cuando una corrida es lenta, hoy no hay forma de
saber si el retraso vino de Kostra, de Supabase o del propio proceso — hay que
adivinar, que es exactamente lo que este proyecto se niega a hacer con la causa
raíz de un incidente. Es un requisito explícito: poder diagnosticar si un
problema de latencia es de la base de datos.

## Decisión

Cada corrida registra el tiempo de cada fase junto con **a qué se lo cobró**.

Tabla `trazas` nueva en Supabase, detallada en
[`modelo-de-datos.md`](../modelo-de-datos.md):

| Columna | Tipo | Nota |
| --- | --- | --- |
| `id` | `uuid` | |
| `corrida_id` | `uuid` | |
| `fase` | `text` | `ingesta` · `triage` · `despacho` · `especialista` · `consolidacion` · `compuerta` · `persistencia` |
| `origen` | `text` | `inferencia` · `almacen` · `local` |
| `detalle` | `text` | `incidente_id` y especialista cuando aplica; ruta PostgREST cuando `origen = 'almacen'` |
| `ms` | `int` | Duración medida |
| `estado` | `text` | `ok` · `fallida` |
| `iniciada_en` | `timestamptz` | |

Más `corridas.duracion_ms` para el total.

**`origen` es la columna que resuelve el requisito.** Sin ella la traza dice
"la fase de especialista tardó 9 s" y no distingue si fueron 8 s de Kostra o
8 s esperando a PostgREST. Con ella, la pregunta de si es latencia de base de
datos se responde sumando `ms where origen = 'almacen'` para una corrida.

**Las filas se acumulan en memoria durante la corrida y se insertan en una
sola escritura al final.** Escribir una traza por paso mediría la latencia de
la base de datos escribiendo en la base de datos: el instrumento contaminaría
la medición y multiplicaría los viajes de red que intenta medir. Un único
`cronometro(fase, origen)` como context manager, envolviendo las llamadas que
ya existen en el módulo de proveedor y en el de almacén, es todo el código
nuevo.

## Alternativas descartadas

| Alternativa | Por qué se descartó |
| --- | --- |
| Solo logs a stdout | Se pierden al cerrar el job de Actions; no se pueden correlacionar con una corrida concreta en el dashboard |
| Un APM externo | Dependencia de runtime nueva, contra el "sin dependencias" del ADR-0001 |
| Medir solo el tiempo total de la corrida | No permite atribuir la lentitud a nada concreto — es el mismo problema que se quiere resolver |
| Medir en el cliente (navegador) | No ve el reparto interno entre fases; solo el tiempo de la petición HTTP completa |
| Insertar una fila de traza por fase, en el momento en que ocurre | El propio insert es una llamada a Supabase: mide la base de datos usando la base de datos, y añade N viajes de red por corrida en vez de uno |

## Consecuencias

**A favor:** una corrida lenta se diagnostica sumando columnas, no adivinando.
El dato queda persistido junto a la corrida, disponible en el dashboard igual
que `llamadas` y `usage`.

**En contra:** una tabla más que mantener y una columna más (`duracion_ms`) en
`corridas`. `detalle` debe evitar cualquier contenido sensible: solo
identificadores y rutas, nunca cuerpos de prompt ni credenciales.

**Coste de revertir:** bajo. `trazas` es aditiva; quitar el cronómetro no
afecta al resto del flujo.
