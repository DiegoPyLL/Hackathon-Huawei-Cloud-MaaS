import json
import unittest

from src.maas_demo.config import Config
from src.maas_demo.orchestrator import MAX_CALLS, MAX_INCIDENTS, Orchestrator, build_tasks, extract_json, validate_triage


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

