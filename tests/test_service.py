import unittest

from src.maas_demo.provider import MockProvider
from src.maas_demo.service import ChatService, ValidationError


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ChatService(MockProvider(model="demo"))

    def test_stream_adds_system_contract_and_returns_metrics(self) -> None:
        events = list(
            self.service.stream([{"role": "user", "content": "Diseña una prueba"}])
        )

        self.assertEqual(events[-1]["type"], "done")
        self.assertGreaterEqual(events[-1]["latency_ms"], 0)
        self.assertEqual(events[-1]["mode"], "mock")

    def test_empty_message_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "vacío"):
            list(self.service.stream([{"role": "user", "content": "   "}]))

    def test_unknown_role_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "role"):
            list(self.service.stream([{"role": "tool", "content": "x"}]))

    def test_history_is_bounded(self) -> None:
        messages = [{"role": "user", "content": str(i)} for i in range(21)]
        with self.assertRaisesRegex(ValidationError, "20"):
            list(self.service.stream(messages))
