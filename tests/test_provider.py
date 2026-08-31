import json
import unittest

from src.maas_demo.provider import MaaSProvider, MockProvider, ProviderError


class FakeResponse:
    def __init__(self, lines: list[bytes]) -> None:
        self.lines = lines

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def __iter__(self):
        return iter(self.lines)


class ProviderTests(unittest.TestCase):
    def test_mock_provider_is_deterministic_and_identifies_mode(self) -> None:
        provider = MockProvider(model="demo-model")
        messages = [{"role": "user", "content": "Reducir tiempos de espera"}]

        first = list(provider.stream(messages))
        second = list(provider.stream(messages))

        self.assertEqual(first, second)
        self.assertEqual(first[-1]["type"], "done")
        self.assertEqual(first[-1]["mode"], "mock")
        self.assertIn("Reducir tiempos", "".join(e.get("delta", "") for e in first))

    def test_maas_provider_parses_v2_stream_without_disabling_tls(self) -> None:
        chunks = [
            {"id": "req-1", "choices": [{"delta": {"content": "Hola "}}]},
            {"id": "req-1", "choices": [{"delta": {"content": "Huawei"}}]},
        ]
        lines = [f"data: {json.dumps(chunk)}\n".encode() for chunk in chunks]
        lines.append(b"data: [DONE]\n")
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return FakeResponse(lines)

        provider = MaaSProvider(
            api_key="secret",
            base_url="https://example.test/v2",
            model="glm-test",
            timeout_seconds=12,
            opener=opener,
        )

        events = list(provider.stream([{"role": "user", "content": "Hola"}]))

        self.assertEqual("".join(e.get("delta", "") for e in events), "Hola Huawei")
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(events[-1]["mode"], "live")
        request, timeout = requests[0]
        self.assertEqual(timeout, 12)
        self.assertEqual(request.full_url, "https://example.test/v2/chat/completions")
        self.assertEqual(request.headers["Authorization"], "Bearer secret")

    def test_maas_provider_rejects_stream_without_content(self) -> None:
        provider = MaaSProvider(
            api_key="secret",
            base_url="https://example.test/v2",
            model="glm-test",
            timeout_seconds=12,
            opener=lambda *_args, **_kwargs: FakeResponse([b"data: [DONE]\n"]),
        )

        with self.assertRaisesRegex(ProviderError, "contenido"):
            list(provider.stream([{"role": "user", "content": "Hola"}]))
