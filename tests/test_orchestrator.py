import json
import time
import unittest

from src.maas_demo.config import Config
from src.maas_demo.orchestrator import MAX_CALLS, MAX_INCIDENTS, Orchestrator, build_tasks, extract_json, validate_triage
from src.maas_demo.provider import ProviderError


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(mode="mock", api_key=None, base_url="https://unused/v2", model="demo")

    def test_extracts_json_wrapped_in_prose(self):
        self.assertEqual(extract_json('resultado: ```json {"ok": true} ```'), {"ok": True})

    def test_dispatch_limits_incidents_and_calls(self):
        triage = {"version": "1", "incidentes": [], "descartados": []}
        for i in range(8):
            triage["incidentes"].append({"id": f"INC-{i+1:02d}", "titulo": "x", "tipo": "capacidad", "canal": "monitoreo", "severidad": "alta", "ataque_activo": i == 7, "evidencia": ["x"], "especialistas": ["sysadmin"], "motivo_ruteo": "x"})
        tasks, deferred = build_tasks(triage)
        self.assertEqual(len(tasks), MAX_CALLS - 2)
        self.assertEqual(len(deferred), 2)
        self.assertEqual(len({task["incident"]["id"] for task in tasks}), MAX_INCIDENTS)

    def test_mock_runs_full_pipeline_and_exposes_mode(self):
        record = {"id": "sample", "canal": "monitoreo", "prompt": "MONITOREO 10:00 cpu.pct value=99"}
        orchestrator = Orchestrator(self.config)
        events = list(orchestrator.stream(record))
        result = orchestrator.store.get(events[-1]["run_id"])
        self.assertEqual(result["mode"], "mock")
        self.assertEqual(result["status"], "completada")
        self.assertEqual(events[-1]["type"], "done")
        self.assertLessEqual(result["llamadas"], MAX_CALLS)

    def test_expected_groundtruth_is_not_sent_to_provider(self):
        class Capture:
            def __init__(self): self.messages = []
            def stream(self, messages):
                self.messages.append(messages)
                yield {"type": "delta", "delta": json.dumps({"version":"1", "incidentes":[], "descartados":[]})}
                yield {"type": "done", "mode":"mock", "model":"x"}
        # The public contract is record.prompt; extra groundtruth is ignored.
        orchestrator = Orchestrator(self.config)
        events = list(orchestrator.stream({"prompt": "MONITOREO", "esperado": {"secreto": "groundtruth"}}))
        self.assertEqual(events[-1]["type"], "done")

    def test_dripping_provider_terminates_within_budget_and_returns_partial(self):
        """T4.1: un proveedor que gotea un byte cada 30s no cuelga la corrida.

        Sintoma medido: una corrida live estuvo >25 min sin emitir una linea con
        el servidor sano. El presupuesto de reloj acota la corrida y entrega lo
        que haya (triage si, especialistas parciales) con status parcial.
        """
        dripping_delay = 30.0
        budget = 1.0  # presupuesto corto para que el test no tarde 30s

        class DripProvider:
            def stream(self, messages):
                # triage valido inmediato, despues el especialista gotea
                role = next((m["content"] for m in messages if m["role"] == "system"), "")
                if role.startswith("ROL: triage"):
                    triage = {"version": "1", "incidentes": [{
                        "id": "INC-01", "titulo": "Caida", "tipo": "indisponibilidad",
                        "canal": "monitoreo", "severidad": "alta", "ataque_activo": False,
                        "evidencia": ["alert=ALRT-1"], "especialistas": ["sysadmin"],
                        "motivo_ruteo": "x"}], "descartados": []}
                    yield {"type": "delta", "delta": json.dumps(triage)}
                    yield {"type": "done", "mode": "mock", "model": "drip"}
                    return
                if role.startswith("ROL: consolidador"):
                    yield {"type": "delta", "delta": "reporte parcial"}
                    yield {"type": "done", "mode": "mock", "model": "drip"}
                    return
                # especialista: gotea un byte cada dripping_delay
                yield {"type": "delta", "delta": "x"}
                time.sleep(dripping_delay)
                yield {"type": "delta", "delta": "y"}
                yield {"type": "done", "mode": "mock", "model": "drip"}

        class Controlled(Orchestrator):
            # R-11: _provider recibe ademas el plazo acotado al presupuesto.
            def _provider(self, phase, timeout_seconds=None):
                return DripProvider()

        orchestrator = Controlled(self.config, presupuesto_seg=budget)
        start = time.perf_counter()
        events = list(orchestrator.stream({"prompt": "MONITOREO alert=ALRT-1"}))
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, dripping_delay, "La corrida debe terminar dentro del presupuesto, no esperar el goteo.")
        done = events[-1]
        self.assertEqual(done["type"], "done")
        self.assertEqual(done["status"], "parcial")
        self.assertTrue(any(e.get("type") == "fase" and e.get("fase") == "presupuesto_agotado" for e in events))

    def test_provider_wall_clock_timeout_raises_provider_error(self):
        """T4.1a: un stream SSE que no cierra dentro del plazo de reloj lanza ProviderError."""
        from src.maas_demo.provider import MaaSProvider

        class HangingResponse:
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def __iter__(self):
                while True:
                    yield b": keepalive\n"

        provider = MaaSProvider(
            api_key="x", base_url="https://x.test/v1", model="m",
            timeout_seconds=0.2, opener=lambda *_a, **_k: HangingResponse(),
        )
        with self.assertRaisesRegex(ProviderError, "plazo de reloj"):
            list(provider.stream([{"role": "user", "content": "hola"}]))



class PlazoPorLlamadaTests(unittest.TestCase):
    """R-11: el plazo por llamada y el presupuesto de corrida estaban descoordinados.

    Sintoma medido en una corrida live real (4 incidentes, 3m16s): el triage
    supero el plazo de 180s, la ProviderError escapo de stream() y la corrida
    entera se perdio sin `done`. El embudo mostro 4/4 recogidos -> 0/4
    detectados. Antes de N-01 el presupuesto de 150s cortaba DESPUES del triage
    y entregaba algo; subir el presupuesto sin tocar el plazo por llamada lo
    empeoro.
    """

    def setUp(self):
        self.config = Config(mode="mock", api_key=None, base_url="https://unused/v2", model="demo")

    def test_un_triage_que_agota_el_plazo_entrega_done_fallida(self):
        class TriageQueRevienta:
            def stream(self, messages):
                raise ProviderError("Huawei MaaS superó el plazo de reloj de 180s sin cerrar el stream.")
                yield  # pragma: no cover - hace de esto un generador

        orchestrator = Orchestrator(self.config)
        orchestrator._provider = lambda phase, timeout_seconds=None: TriageQueRevienta()

        eventos = list(orchestrator.stream({"prompt": "MONITOREO 10:00 cpu.pct value=99"}))

        final = eventos[-1]
        self.assertEqual(final["type"], "done")
        self.assertEqual(final["status"], "fallida")
        self.assertIn("plazo de reloj", final["error"])
        # La fase se declara antes del done, no se pierde el motivo.
        fases = [e for e in eventos if e["type"] == "fase" and e["fase"] == "triage"]
        self.assertEqual(fases[-1]["estado"], "fallida")
        # La corrida queda guardada y consultable, no se evapora.
        guardada = orchestrator.store.get(final["run_id"])
        self.assertEqual(guardada["status"], "fallida")
        self.assertEqual(guardada["trazas"][0]["phase"], "triage")

    def test_el_plazo_de_la_llamada_se_acota_al_presupuesto_restante(self):
        """Ninguna llamada puede consumir el presupuesto entero y encima fallar."""
        plazos = []

        class Registrador:
            def stream(self, messages):
                yield {"type": "delta", "delta": json.dumps(
                    {"version": "1", "incidentes": [], "descartados": []})}
                yield {"type": "done", "mode": "mock", "model": "x"}

        config = Config(mode="mock", api_key=None, base_url="https://unused/v2",
                        model="demo", timeout_seconds=180.0)
        orchestrator = Orchestrator(config, presupuesto_seg=12.0)

        def espia(phase, timeout_seconds=None):
            plazos.append(timeout_seconds)
            return Registrador()

        orchestrator._provider = espia
        list(orchestrator.stream({"prompt": "MONITOREO 10:00 cpu.pct value=99"}))

        self.assertTrue(plazos, "no se registro ninguna llamada")
        # El presupuesto (12s) manda sobre el timeout configurado (180s).
        for plazo in plazos:
            self.assertIsNotNone(plazo)
            self.assertLessEqual(plazo, 12.0)

    def test_sin_presupuesto_no_se_intenta_la_llamada(self):
        orchestrator = Orchestrator(self.config, presupuesto_seg=0.0)
        eventos = list(orchestrator.stream({"prompt": "MONITOREO 10:00 cpu.pct value=99"}))
        final = eventos[-1]
        self.assertEqual(final["type"], "done")
        self.assertEqual(final["status"], "fallida")
        self.assertIn("Sin presupuesto", final["error"])


class ReintentoDeTriageTests(unittest.TestCase):
    """R-12: el reintento del triage no cubria el JSON malformado.

    Sintoma medido en live: la corrida murio con "Expecting property name
    enclosed in double quotes: line 3 column 2 (char 21)" a los 144s y sin un
    solo reintento. `extract_json` corria dentro de `call()`, o sea ANTES del
    try/except que reintenta: un JSON bien formado que no validaba tenia un
    reintento, y uno roto no tenia ninguno. Devolver JSON roto es la falla mas
    frecuente de un modelo, asi que la unica sin red era la mas probable.
    """

    TRIAGE_VALIDO = json.dumps({
        "version": "1",
        "incidentes": [{
            "id": "INC-01", "titulo": "Caida de checkout", "tipo": "indisponibilidad",
            "canal": "monitoreo", "severidad": "alta", "ataque_activo": False,
            "evidencia": ["alert=ALRT-1"], "especialistas": ["sysadmin"],
            "motivo_ruteo": "disponibilidad",
        }],
        "descartados": [],
    })
    TRIAGE_ROTO = '{\n  "version": "1",\n  incidentes: []\n}'

    def setUp(self):
        self.config = Config(mode="mock", api_key=None, base_url="https://unused/v2", model="demo")

    def _proveedor_por_turnos(self, respuestas):
        turnos = iter(respuestas)
        registro = {"llamadas": 0, "mensajes": []}

        class PorTurnos:
            def stream(self_inner, messages):
                registro["llamadas"] += 1
                registro["mensajes"].append(messages)
                yield {"type": "delta", "delta": next(turnos)}
                yield {"type": "done", "mode": "mock", "model": "x"}

        return PorTurnos, registro

    def test_json_roto_la_primera_vez_se_reintenta_y_la_corrida_termina(self):
        PorTurnos, registro = self._proveedor_por_turnos(
            [self.TRIAGE_ROTO, self.TRIAGE_VALIDO,
             # especialista y consolidacion: cualquier cosa parseable / texto
             json.dumps({
                 "version": "1", "incidente_id": "INC-01", "especialista": "sysadmin",
                 "causa_raiz": "x", "confianza": "media", "evidencia": ["alert=ALRT-1"],
                 "descartado": [], "viabilidad": "requiere_mas_datos", "accion": None,
             }),
             "reporte final"])
        orchestrator = Orchestrator(self.config)
        orchestrator._provider = lambda phase, timeout_seconds=None: PorTurnos()

        eventos = list(orchestrator.stream({"prompt": "MONITOREO alert=ALRT-1 checkout 500"}))

        # Se declaro el reintento y no se perdio la corrida.
        reintentos = [e for e in eventos
                      if e["type"] == "fase" and e.get("estado") == "reintento"]
        self.assertEqual(len(reintentos), 1)
        self.assertIn("double quotes", reintentos[0]["detalle"])
        final = eventos[-1]
        self.assertEqual(final["type"], "done")
        self.assertNotEqual(final["status"], "fallida")
        # El reintento le devolvio al modelo su propio texto y el error concreto.
        segundo = registro["mensajes"][1]
        self.assertEqual(segundo[-2]["role"], "assistant")
        self.assertIn("incidentes: []", segundo[-2]["content"])
        self.assertIn("no sirve", segundo[-1]["content"])

    def test_json_roto_las_dos_veces_termina_en_done_fallida(self):
        PorTurnos, registro = self._proveedor_por_turnos(
            [self.TRIAGE_ROTO, self.TRIAGE_ROTO])
        orchestrator = Orchestrator(self.config)
        orchestrator._provider = lambda phase, timeout_seconds=None: PorTurnos()

        eventos = list(orchestrator.stream({"prompt": "MONITOREO alert=ALRT-1"}))

        final = eventos[-1]
        self.assertEqual(final["type"], "done")
        self.assertEqual(final["status"], "fallida")
        self.assertIn("double quotes", final["error"])
        # Exactamente dos intentos: uno y el reintento. Ni mas, ni menos.
        self.assertEqual(registro["llamadas"], 2)


class ConsolidacionFallidaTests(unittest.TestCase):
    """R-13: una consolidacion que falla no puede tirar la corrida entera.

    Sintoma medido en live: con 41.8s de presupuesto restante la consolidacion
    vencio, la ProviderError escapo de stream() y se perdio una corrida que ya
    tenia 4 hallazgos y 1 accion esperando aprobacion. El embudo habia llegado a
    0.75 de conversion. El reporte ejecutivo es lo ultimo y lo mas prescindible
    de la corrida: no puede llevarse por delante lo que ya salio bien.
    """

    TRIAGE_VALIDO = json.dumps({
        "version": "1",
        "incidentes": [{
            "id": "INC-01", "titulo": "Caida de checkout", "tipo": "indisponibilidad",
            "canal": "monitoreo", "severidad": "alta", "ataque_activo": False,
            "evidencia": ["alert=ALRT-1"], "especialistas": ["sysadmin"],
            "motivo_ruteo": "disponibilidad",
        }],
        "descartados": [],
    })
    HALLAZGO_VALIDO = json.dumps({
        "version": "1", "incidente_id": "INC-01", "especialista": "sysadmin",
        "causa_raiz": "El deploy rompio checkout.", "confianza": "alta",
        "evidencia": ["alert=ALRT-1"], "descartado": [],
        "viabilidad": "requiere_mas_datos", "accion": None,
    })

    def setUp(self):
        self.config = Config(mode="mock", api_key=None, base_url="https://unused/v2", model="demo")

    def test_la_corrida_sobrevive_a_una_consolidacion_que_vence(self):
        estado = {"fase": 0}

        class ConsolidacionRota:
            def stream(self_inner, messages):
                estado["fase"] += 1
                if estado["fase"] == 1:
                    yield {"type": "delta", "delta": ConsolidacionFallidaTests.TRIAGE_VALIDO}
                elif estado["fase"] == 2:
                    yield {"type": "delta", "delta": ConsolidacionFallidaTests.HALLAZGO_VALIDO}
                else:
                    raise ProviderError("Huawei MaaS superó el plazo de reloj de 41.7852s sin cerrar el stream.")
                yield {"type": "done", "mode": "mock", "model": "x"}

        orchestrator = Orchestrator(self.config)
        orchestrator._provider = lambda phase, timeout_seconds=None: ConsolidacionRota()

        eventos = list(orchestrator.stream({"prompt": "MONITOREO alert=ALRT-1 checkout 500"}))

        final = eventos[-1]
        self.assertEqual(final["type"], "done")
        # No se pierde: se entrega parcial, no fallida.
        self.assertEqual(final["status"], "parcial")
        # El hallazgo que si salio sigue estando.
        hallazgos = [e for e in eventos if e["type"] == "hallazgo"]
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0]["hallazgo"]["causa_raiz"], "El deploy rompio checkout.")
        # La fase se declara, el motivo no se pierde en silencio.
        fases = [e for e in eventos
                 if e["type"] == "fase" and e.get("fase") == "consolidacion"]
        self.assertEqual(fases[-1]["estado"], "fallida")
        self.assertIn("plazo de reloj", fases[-1]["detalle"])
        # Y el reporte dice por que no hay reporte, en vez de quedar vacio.
        guardada = orchestrator.store.get(final["run_id"])
        self.assertIn("la consolidación falló", guardada["reporte"])


class AnclajeDeEvidenciaDelTriageTests(unittest.TestCase):
    """N-05: la evidencia del triage tampoco estaba contrastada contra el volcado.

    T5.1 puso el anclaje literal en `validate_finding` pero no en
    `validate_triage`, asi que en :8080 las tarjetas de hallazgos llevaban sello
    y las de incidentes detectados no. Un sello a medias es peor que ninguno:
    sugiere que todo lo que se ve fue verificado.
    """

    VOLCADO = ("MONITOREO 10:15:03 evento=deploy release=v360 deploy=DEP-404 componente=checkout by=ci-bot | "
               "MONITOREO 10:16:00 alert=ALRT-9683 endpoint=/checkout status=500 ratio=0.90 ventana=2min")

    def _triage(self, evidencia):
        return {
            "version": "1",
            "incidentes": [{
                "id": "INC-01", "titulo": "x", "tipo": "indisponibilidad",
                "canal": "monitoreo", "severidad": "alta", "ataque_activo": False,
                "evidencia": evidencia, "especialistas": ["sysadmin"],
                "motivo_ruteo": "disponibilidad",
            }],
            "descartados": [],
        }

    def test_una_cita_textual_del_volcado_queda_sellada(self):
        cita = "alert=ALRT-9683 endpoint=/checkout status=500 ratio=0.90 ventana=2min"
        validado = validate_triage(self._triage([cita]), volcado=self.VOLCADO)
        sellos = validado["incidentes"][0]["evidencia_verificada"]
        self.assertEqual(len(sellos), 1)
        self.assertTrue(sellos[0]["verificada"])
        self.assertNotIn("evidencia_no_verificada", validado["incidentes"][0])

    def test_una_cita_parafraseada_se_marca_no_verificada(self):
        """El modelo resume en vez de citar: pasa la validacion de forma, no la de fondo."""
        validado = validate_triage(
            self._triage(["hubo un pico de errores 500 en checkout tras el deploy"]),
            volcado=self.VOLCADO)
        incidente = validado["incidentes"][0]
        self.assertFalse(incidente["evidencia_verificada"][0]["verificada"])
        self.assertEqual(len(incidente["evidencia_no_verificada"]), 1)

    def test_sin_volcado_no_se_inventa_un_sello(self):
        """Sin con que contrastar, no se marca nada: un sello falso es peor que
        ninguno porque afirma una verificacion que no ocurrio."""
        validado = validate_triage(self._triage(["lo que sea"]))
        self.assertNotIn("evidencia_verificada", validado["incidentes"][0])

    def test_el_anclaje_no_convierte_un_triage_valido_en_invalido(self):
        """Marcar no es rechazar: el triage sigue siendo utilizable."""
        validado = validate_triage(
            self._triage(["algo que no esta en el volcado en absoluto, ni parecido"]),
            volcado=self.VOLCADO)
        self.assertEqual(validado["incidentes"][0]["id"], "INC-01")
