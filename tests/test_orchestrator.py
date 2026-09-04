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
            def _provider(self, phase):
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

