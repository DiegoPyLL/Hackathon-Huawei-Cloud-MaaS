import json
import threading
import unittest
import urllib.request

from src.maas_demo.config import Config
from src.maas_demo.server import create_server


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        config = Config(mode="mock", api_key=None, base_url="https://unused/v2", model="demo")
        self.server = create_server(config, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_exposes_mock_mode(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/api/health") as response:
            payload = json.load(response)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "mock")

    def test_stream_endpoint_emits_delta_and_done(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/chat/stream",
            data=json.dumps(
                {"messages": [{"role": "user", "content": "Demo Huawei"}]}
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            body = response.read().decode()

        self.assertIn('"type": "delta"', body)
        self.assertIn('"type": "done"', body)
        self.assertIn('"mode": "mock"', body)


if __name__ == "__main__":
    unittest.main()
