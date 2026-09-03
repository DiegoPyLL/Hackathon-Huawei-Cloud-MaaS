"""Pruebas de contrato y de extremo a extremo del vertical slice.

No usa red externa: las respuestas del proveedor live se simulan en el borde
del adaptador y el resto del flujo se ejecuta tal como lo haria la aplicacion.
"""

import json
import importlib.util
import threading
import unittest
import urllib.error
import urllib.request
from http import HTTPStatus
from unittest.mock import patch
from pathlib import Path

from src.maas_demo.config import Config, ConfigError

try:
    from src.maas_demo.orchestrator import (
        ACTION_CATALOG,
        Orchestrator,
        validate_finding,
        validate_triage,
    )
    HAY_ORQUESTADOR = True
except ImportError:  # aun vive en la rama agente-orquestrador-*, no en main
    HAY_ORQUESTADOR = False
    ACTION_CATALOG = {}
    Orchestrator = None
    validate_finding = validate_triage = None

SIN_ORQUESTADOR = "src/maas_demo/orchestrator.py aun no esta en main"
from src.maas_demo.provider import MaaSProvider, MockProvider, ProviderError
from src.maas_demo.server import MAX_REQUEST_BYTES, create_server
from src.maas_demo.service import ChatService, MAX_CONTENT_LENGTH, MAX_MESSAGES, ValidationError


def load_script(name):
    path = Path(__file__).parents[1] / "scripts" / "ejecutablesBase" / name
    spec = importlib.util.spec_from_file_location(name.replace(".", "_"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def event_stream(value: object, *, mode: str = "mock"):
    yield {"type": "delta", "delta": json.dumps(value, ensure_ascii=False)}
    yield {"type": "done", "mode": mode, "model": "test-model", "request_id": "test-request"}


def valid_triage(*, specialists=None, active=False):
    return {
        "version": "1",
        "incidentes": [{
            "id": "INC-01", "titulo": "Caida de prueba", "tipo": "indisponibilidad",
            "canal": "monitoreo", "severidad": "alta", "ataque_activo": active,
            "evidencia": ["alert=ALRT-1"], "especialistas": specialists or ["sysadmin"],
            "motivo_ruteo": "La señal coincide con la tabla canónica.",
        }],
        "descartados": [],
    }


def valid_finding(incident, specialist="sysadmin", action=None):
    return {
        "version": "1", "incidente_id": incident["id"], "especialista": specialist,
        "causa_raiz": "La evidencia requiere confirmacion.", "confianza": "media",
        "evidencia": ["alert=ALRT-1"], "descartado": [], "viabilidad": "accionable",
        "accion": action,
    }


class ProviderEdgeTests(unittest.TestCase):
    def test_live_request_serializes_contract_and_never_prints_key(self):
        requests = []

        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def __iter__(self):
                yield b'data: {"id":"r1","choices":[{"delta":{"content":"ok"}}]}\n'
                yield b'data: [DONE]\n'

        def opener(request, timeout):
            requests.append((request, timeout))
            return Response()

        key = "unit-test-secret"
        provider = MaaSProvider(api_key=key, base_url="https://maas.test/v1/chat/completions",
                                model="m", timeout_seconds=7, opener=opener)
        events = list(provider.stream([{"role": "user", "content": "hola"}]))
        request, timeout = requests[0]
        self.assertEqual(timeout, 7)
        self.assertEqual(request.full_url, "https://maas.test/v1/chat/completions")
        self.assertEqual(json.loads(request.data), {"model": "m", "stream": True,
                                                     "messages": [{"role": "user", "content": "hola"}]})
        self.assertEqual(request.get_header("Authorization"), f"Bearer {key}")
        self.assertEqual(events[-1]["mode"], "live")

    def test_sse_ignores_comments_empty_lines_and_non_data(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def __iter__(self):
                return iter([b": keepalive\n", b"\n", b"event: message\n",
                             b'data: {"choices":[{"delta":{"content":"a"}}]}\n',
                             b'data: {"choices":[]}\n', b"data: [DONE]\n"])
        provider = MaaSProvider(api_key="x", base_url="https://x.test/v1", model="m",
                                timeout_seconds=1, opener=lambda *_args, **_kwargs: Response())
        self.assertEqual("a", "".join(e.get("delta", "") for e in provider.stream([])))

    def test_sse_malformed_json_and_transport_errors_are_normalized(self):
        class Bad:
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def __iter__(self): return iter([b"data: nope\n"])
        provider = MaaSProvider(api_key="x", base_url="https://x.test/v1", model="m",
                                timeout_seconds=1, opener=lambda *_a, **_k: Bad())
        with self.assertRaisesRegex(ProviderError, "SSE inválido"):
            list(provider.stream([]))
        http_error = urllib.error.HTTPError("https://x.test", 429, "busy", {}, None)
        provider.opener = lambda *_a, **_k: (_ for _ in ()).throw(http_error)
        with self.assertRaisesRegex(ProviderError, "HTTP 429"):
            list(provider.stream([]))

    def test_mock_unknown_role_still_returns_mock_and_content(self):
        events = list(MockProvider().stream([{"role": "system", "content": "unknown"},
                                             {"role": "user", "content": "x"}]))
        self.assertEqual(events[-1]["mode"], "mock")
        self.assertTrue(any(e.get("delta") for e in events))


class ServiceContractTests(unittest.TestCase):
    def test_service_trims_messages_and_injects_system_only(self):
        class Capture:
            def __init__(self): self.messages = None
            def stream(self, messages):
                self.messages = list(messages)
                yield {"type": "delta", "delta": "respuesta"}
                yield {"type": "done", "mode": "mock", "model": "test-model"}
        provider = Capture()
        result = ChatService(provider).complete([{"role": "user", "content": "  hola  "}])
        self.assertEqual(provider.messages[0]["role"], "system")
        self.assertEqual(provider.messages[-1]["content"], "hola")
        self.assertEqual(result["content"], "respuesta")
        self.assertIsInstance(result["latency_ms"], int)

    def test_all_message_boundary_rules(self):
        service = ChatService(MockProvider())
        cases = [([], "no vacía"), ([{"role": "assistant", "content": "x"}], "último"),
                 ([{"role": "user", "content": "x"}] * (MAX_MESSAGES + 1), "20"),
                 ([{"role": "user", "content": "x" * (MAX_CONTENT_LENGTH + 1)}], "supera"),
                 (["x"], "objeto"), ([{"role": "user"}], "content")]
        for messages, expected in cases:
            with self.subTest(expected=expected), self.assertRaisesRegex(ValidationError, expected):
                list(service.stream(messages))


@unittest.skipUnless(HAY_ORQUESTADOR, SIN_ORQUESTADOR)
class OrchestratorContractTests(unittest.TestCase):
    def test_triage_rejects_each_key_shape_violation(self):
        base = valid_triage()
        mutations = [({"version": "2"}, "version"), ({"incidentes": "x"}, "version"),
                     ({"id": "bad"}, "id"), ({"tipo": "inventado"}, "taxonomía"),
                     ({"canal": "api"}, "canal"), ({"severidad": "urgente"}, "severidad"),
                     ({"ataque_activo": "no"}, "booleano"), ({"evidencia": []}, "evidencia"),
                     ({"especialistas": ["fraude"]}, "especialistas"), ({"motivo_ruteo": ""}, "motivo")]
        for change, expected in mutations:
            value = json.loads(json.dumps(base))
            target = value["incidentes"][0]
            if "version" in change: value["version"] = change["version"]
            elif "incidentes" in change: value["incidentes"] = change["incidentes"]
            else: target.update(change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, expected):
                validate_triage(value)

    def test_finding_rejects_wrong_task_invalid_action_and_incompatible_action(self):
        incident = valid_triage()["incidentes"][0]
        with self.assertRaisesRegex(ValueError, "no coincide"):
            validate_finding(valid_finding(incident, "dba"), incident, "sysadmin")
        with self.assertRaisesRegex(ValueError, "action_id"):
            validate_finding(valid_finding(incident, action={"action_id": "rm", "params": {}}), incident, "sysadmin")
        weak = valid_finding(incident, action={"action_id": "bloquear_ip", "params": {}})
        weak["confianza"] = "insuficiente"
        with self.assertRaisesRegex(ValueError, "acción"):
            validate_finding(weak, incident, "sysadmin")

    def test_full_pipeline_creates_human_approval_and_persists_run(self):
        config = Config(mode="mock", api_key=None, base_url="https://unused", model="m")
        triage = valid_triage(active=True)
        action = {"action_id": "bloquear_ip", "params": {"ip": "203.0.113.5"}}
        incident = triage["incidentes"][0]

        class Controlled(Orchestrator):
            def _provider(self, phase):
                value = triage if phase == "triage" else valid_finding(incident, action=action) if phase == "especialista" else "Reporte final"
                return type("P", (), {"stream": lambda self, messages: event_stream(value, mode="mock")})()

        orchestrator = Controlled(config)
        events = list(orchestrator.stream({"canal": "monitoreo", "prompt": "evidencia"}))
        done = events[-1]
        result = orchestrator.store.get(done["run_id"])
        self.assertEqual(done["status"], "completada")
        self.assertEqual(result["llamadas"], 3)
        self.assertEqual(len(result["aprobaciones"]), 1)
        self.assertEqual(result["aprobaciones"][0]["estado"], "pendiente")
        self.assertTrue(any(e["type"] == "aprobacion" for e in events))

    def test_failed_specialist_is_partial_and_does_not_abort_other_tasks(self):
        config = Config(mode="mock", api_key=None, base_url="https://unused", model="m")
        triage = valid_triage(specialists=["sysadmin", "dba"])
        incident = triage["incidentes"][0]

        class Controlled(Orchestrator):
            def _provider(self, phase):
                if phase == "triage": value = triage
                elif phase == "consolidacion": value = "reporte"
                else:
                    class Broken:
                        def stream(self, _): raise ProviderError("especialista caído")
                    return Broken()
                return type("P", (), {"stream": lambda self, messages: event_stream(value)})()

        result = list(Controlled(config).stream({"prompt": "x"}))[-1]
        self.assertEqual(result["status"], "parcial")
        self.assertEqual(result["fallidos"], 2)

    def test_invalid_record_fails_before_ingesta(self):
        config = Config(mode="mock", api_key=None, base_url="https://unused", model="m")
        with self.assertRaisesRegex(ValueError, "prompt"):
            list(Orchestrator(config).stream({"prompt": "  "}))


class HttpEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(mode="mock", api_key=None, base_url="https://unused", model="demo")
        self.server = create_server(self.config, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)

    def request(self, path, *, method="GET", body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers=headers or ({"Content-Type": "application/json"} if data else {}))
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()

    def test_health_static_unknown_route_and_security_headers(self):
        status, headers, body = self.request("/api/health")
        self.assertEqual(status, 200); self.assertEqual(json.loads(body)["mode"], "mock")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(self.request("/does-not-exist")[0], HTTPStatus.NOT_FOUND)
        self.assertEqual(self.request("/")[0], HTTPStatus.OK)

    def test_http_validation_and_size_errors_are_json_400(self):
        for body in (b"not-json", b"[]"):
            request = urllib.request.Request(self.base + "/api/chat/stream", data=body,
                                             method="POST", headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(request)
            except urllib.error.HTTPError as error:
                self.assertEqual(error.code, 400)
                self.assertIn("error", json.loads(error.read()))
        request = urllib.request.Request(self.base + "/api/chat/stream", data=b"{}", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request)
        self.assertEqual(context.exception.code, 400)
        self.assertEqual(self.request("/api/chat/stream", method="POST", body={"messages": []})[0], 400)
        oversized = urllib.request.Request(self.base + "/api/chat/stream", data=b"x", method="POST",
                                            headers={"Content-Length": str(MAX_REQUEST_BYTES + 1)})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(oversized)
        self.assertEqual(context.exception.code, 400)

    @unittest.skipUnless(HAY_ORQUESTADOR, SIN_ORQUESTADOR)
    def test_chat_and_incident_streams_are_parseable_sse_and_run_is_retrievable(self):
        status, headers, body = self.request("/api/chat/stream", method="POST",
                                              body={"messages": [{"role": "user", "content": "hola"}]})
        self.assertEqual(status, 200); self.assertIn("text/event-stream", headers["Content-Type"])
        events = [json.loads(line[6:]) for line in body.decode().splitlines() if line.startswith("data:")]
        self.assertEqual(events[-1]["type"], "done"); self.assertEqual(events[-1]["mode"], "mock")
        _, _, incident_body = self.request("/api/incidentes/run", method="POST",
                                            body={"prompt": "MONITOREO cpu.pct value=99"})
        incident_events = [json.loads(line[6:]) for line in incident_body.decode().splitlines() if line.startswith("data:")]
        run_id = incident_events[-1]["run_id"]
        self.assertEqual(self.request("/api/corridas/" + run_id)[0], 200)
        self.assertEqual(self.request("/api/corridas/nope")[0], 404)

    def test_unknown_post_and_approval_not_found(self):
        self.assertEqual(self.request("/api/nope", method="POST", body={})[0], 404)
        self.assertEqual(self.request("/api/aprobaciones/nope", method="POST", body={"decision": "aprobada"})[0], 404)


class ConfigSecurityTests(unittest.TestCase):
    def test_live_requires_https_and_valid_timeout_and_supabase_https(self):
        env = {"MAAS_MODE": "live", "MAAS_API_KEY": "x", "MAAS_BASE_URL": "http://bad"}
        with patch.dict("os.environ", env, clear=True), self.assertRaisesRegex(ConfigError, "HTTPS"):
            Config.from_env()
        with patch.dict("os.environ", {"MAAS_TIMEOUT_SECONDS": "0"}, clear=True), self.assertRaisesRegex(ConfigError, "entre"):
            Config.from_env()
        with patch.dict("os.environ", {"SUPABASE_URL": "http://bad"}, clear=True), self.assertRaisesRegex(ConfigError, "SUPABASE"):
            Config.from_env()

    def test_provider_factory_does_not_make_live_without_key(self):
        with patch.dict("os.environ", {"MAAS_MODE": "live"}, clear=True):
            with self.assertRaises(ConfigError): Config.from_env()


class ExecutableFlowTests(unittest.TestCase):
    def test_evaluator_rejects_empty_or_non_list_dataset(self):
        evaluator = load_script("evaluar.py")
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            for value in ({}, []):
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.subTest(value=value), self.assertRaises(ValueError):
                    evaluator.load_cases(path)

    def test_evaluator_marks_provider_failure_without_fallback(self):
        evaluator = load_script("evaluar.py")

        class Broken:
            def complete(self, _): raise ProviderError("live no disponible")

        result = evaluator.evaluate_case(Broken(), {"id": "x", "segment": "live", "prompt": "p"})
        self.assertFalse(result["passed"])
        self.assertEqual(result["error"], "live no disponible")

    def test_smoke_parser_requires_content_and_done(self):
        smoke = load_script("prueba-humo.py")

        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def __iter__(self):
                return iter([b'data: {"type":"delta","delta":"ok"}\n',
                             b'data: {"type":"done","mode":"live","model":"m","latency_ms":1}\n'])

        with patch.object(smoke.urllib.request, "urlopen", return_value=Response()):
            result = smoke.stream_once("https://example.test")
        self.assertEqual(result["mode"], "live")

        class Empty(Response):
            def __iter__(self): return iter([b'data: {"type":"done","mode":"mock"}\n'])
        with patch.object(smoke.urllib.request, "urlopen", return_value=Empty()):
            with self.assertRaisesRegex(RuntimeError, "no entregó"):
                smoke.stream_once("https://example.test")


if __name__ == "__main__":
    unittest.main()
