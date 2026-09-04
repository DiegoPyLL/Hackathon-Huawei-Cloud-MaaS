# Protocolo de trabajo nocturno

Este archivo manda sobre cualquier otra instrucción. Si algo aquí choca con lo
que te parece buena idea, gana esto.

## El bucle

Una vuelta = una tarea. No dos, no media.

1. Abrí `noche/BACKLOG.md` y tomá **la primera tarea sin marcar** (`- [ ]`).
   En orden. No elijas la que te parece más fácil ni la más divertida.
2. Si no queda ninguna → andá a **Modo guardia** (abajo). No inventes trabajo.
3. Trabajá **solo esa tarea**, y solo en los archivos que la tarea nombra.
4. Corré la compuerta:

   ```
   .venv\Scripts\python.exe scripts/ejecutablesBase/compuerta.py
   ```

   Antes de correrla tenés que haber commiteado, porque la compuerta exige el
   árbol limpio. Entonces el orden real es: escribís → `git add` → `git commit`
   → compuerta.

   - **Sale 0** → marcá la tarea `- [x]` en el backlog, escribí la entrada en
     `noche/BITACORA.md`, commiteá esos dos archivos y `git push`.
   - **Sale 1** → `git reset --hard HEAD~1` para deshacer la tarea, marcá la
     tarea como `- [!] BLOQUEADA: <motivo en una línea>` en el backlog,
     anotalo en la bitácora, commiteá **solo** el backlog y la bitácora, y
     seguí con la siguiente. No insistas más de **dos** intentos en la misma
     tarea.
5. Volvé al paso 1.

## Reglas que no se negocian

- **Nunca toques un test para que pase.** Si un test es genuinamente incorrecto,
  la tarea se declara BLOQUEADA y se explica por qué. Borrar, saltear
  (`@skip`), aflojar un assert o bajar el conteo de tests es la única forma de
  arruinar esto de verdad, y la compuerta lo detecta con el trinquete.
- **Un commit por tarea.** El mensaje dice el síntoma que arregla, no solo el
  qué. Así se puede bisectar por la mañana.
- **El árbol nunca queda sucio.** Cada vuelta termina commiteada o revertida.
  Te pueden matar el proceso en cualquier momento y el repo tiene que estar sano.
- **Rama propia.** Todo va a `noche-<AAAA-MM-DD>`. Nunca a `main`. Nunca
  `--force`, nunca `filter-repo`, nunca reescribir historia.
- **No agregues dependencias.** El proyecto es stdlib pura en `src/`; el resto
  usa lo que ya está en `.venv`. Si una tarea parece necesitar una librería
  nueva, está mal entendida: declarala BLOQUEADA.
- **No refactorices de paso.** Si ves algo feo fuera del alcance de la tarea,
  anotalo al final del backlog como tarea nueva y seguí. "Ya que estoy" es como
  se rompen los repos de madrugada.
- **No toques**: `.env`, `.git/`, `reinforcement-range/`, `.claude/skills/`,
  ni ningún archivo con credenciales.
- **No llames a `live`.** Todo el trabajo nocturno es en `mock`. Una corrida
  live cuesta minutos y cuota, y no hay nadie mirando. La única excepción está
  declarada en la tarea N-02.
- **Si una tarea ya está hecha**, marcala `- [x] (ya estaba)` y seguí. No la
  rehagas.

## Invariantes del proyecto (de AGENTS.md)

Ninguna tarea puede romper esto:

- `mock` y `live` siempre visibles. Un fallo `live` nunca se convierte en éxito
  `mock` silencioso.
- `MAAS_API_KEY` solo en backend. Nunca al navegador, nunca al repo.
- El dominio depende del contrato `ChatProvider`, no de URLs de Huawei.
- El Agente 1 es de solo lectura. Las acciones se proponen y esperan a un
  humano (ADR-0004).
- El agente **nunca** ve el groundtruth del bus. La trazabilidad vive en el
  puente por eso; no muevas esa lógica hacia `src/maas_demo/`.

## La bitácora

Una entrada por vuelta, al final de `noche/BITACORA.md`, en este formato:

```
## N-07 · Mock determinista · 03:14
Estado: HECHA
Commit: a1b2c3d
Qué cambió: MockProvider ahora reconoce evento=deploy y devuelve indisponibilidad.
Verificación: compuerta verde, 164 tests (+5).
Nota: el escenario de locks sigue cayendo en degradacion; lo dejé para N-11.
```

Si fue BLOQUEADA, `Estado: BLOQUEADA` y el motivo concreto. La bitácora es lo
que se lee a las 7am para saber qué pasó sin leer 40 commits.

## Modo guardia

Cuando el backlog se vacía, **no inventes features**. Entrás en un ciclo corto
y acotado, y en cada vuelta hacés una sola de estas, rotando:

1. Correr la compuerta completa y anotar el resultado en la bitácora.
2. Correr `python scripts/ejecutablesBase/evaluar.py --mode mock` y
   `--cases evals/casos-multi-incidente.json`, anotar si algo cambió.
3. Leer un archivo de `docs/` y verificar que lo que afirma sigue siendo cierto
   contra el código. Si no lo es, corregir **la documentación** (nunca el
   código para que encaje con el doc).
4. Buscar en el repo comentarios `TODO`/`FIXME` y anotarlos como tareas nuevas
   al final del backlog. Sin resolverlos.

Entre vuelta y vuelta del modo guardia, esperá. No hace falta quemar tokens
girando en vacío: si no hay nada que hacer, anotá "sin cambios" y frená.

## Cuándo parar

- Backlog vacío y dos vueltas seguidas de modo guardia sin encontrar nada →
  escribí `noche/RESUMEN.md` con: tareas hechas, bloqueadas y por qué,
  conteo de tests inicial y final, y las tres cosas que recomendás mirar
  primero por la mañana. Después frená.
- Tres tareas BLOQUEADAS seguidas → frená y escribí el resumen. Algo
  estructural está mal y seguir empeora las cosas.
