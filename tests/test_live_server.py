"""Pruebas del servidor de la demo en vivo (:8001)."""

import importlib.util
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def cargar_live_server():
    ruta = RAIZ / "projects" / "devchat-generator" / "demo" / "live_server.py"
    spec = importlib.util.spec_from_file_location("live_server", ruta)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class DerivarHealthTest(unittest.TestCase):
    """N-09: health se deriva de las métricas mostradas, no de un flag pegajoso."""

    def setUp(self):
        self.modulo = cargar_live_server()

    def test_metricas_sanas_dan_healthy(self):
        m = {"latency": 250, "error_rate": 0.01, "disk": 45}
        self.assertEqual(self.modulo._derivar_health(m), "healthy")

    def test_latencia_alta_dan_unhealthy(self):
        m = {"latency": 900, "error_rate": 0.01, "disk": 45}
        self.assertEqual(self.modulo._derivar_health(m), "unhealthy")

    def test_error_rate_alto_dan_unhealthy(self):
        m = {"latency": 250, "error_rate": 0.06, "disk": 45}
        self.assertEqual(self.modulo._derivar_health(m), "unhealthy")

    def test_disco_alto_dan_unhealthy(self):
        m = {"latency": 250, "error_rate": 0.01, "disk": 90}
        self.assertEqual(self.modulo._derivar_health(m), "unhealthy")

    def test_metricas_en_el_limite_dan_healthy(self):
        m = {"latency": 800, "error_rate": 0.05, "disk": 85}
        self.assertEqual(self.modulo._derivar_health(m), "healthy")


if __name__ == "__main__":
    unittest.main()
