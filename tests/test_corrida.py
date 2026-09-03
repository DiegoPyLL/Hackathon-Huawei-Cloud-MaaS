"""Pruebas del entrypoint único de corrida.

Carga el script por ruta, igual que `test_devkit_setup.py`, porque el nombre
lleva guion y no es importable.
"""

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from src.maas_demo.config import Config
from src.maas_demo.provider import MockProvider, ProviderError
from src.maas_demo.service import ChatService


RAIZ = Path(__file__).resolve().parents[1]


def cargar_script():
    ruta = RAIZ / "scripts" / "ejecutablesBase" / "ejecutar-corrida.py"
    spec = importlib.util.spec_from_file_location("ejecutar_corrida", ruta)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


corrida = cargar_script()


class DatasetTests(unittest.TestCase):
    def test_lee_el_dataset_de_monitoreo_por_defecto(self) -> None:
        self.assertTrue(corrida.DATASET_MONITOREO.is_file())
        casos = corrida.cargar_volcados(corrida.DATASET_MONITOREO)
        self.assertTrue(casos)
        self.assertIn("prompt", casos[0])
        self.assertIn("esperado", casos[0])

    def test_acepta_jsonl_y_json(self) -> None:
        with TemporaryDirectory() as directorio:
            jsonl = Path(directorio) / "d.jsonl"
            jsonl.write_text('{"id":"a","prompt":"x"}\n{"id":"b","prompt":"y"}\n', encoding="utf-8")
            self.assertEqual(len(corrida.cargar_volcados(jsonl)), 2)

            plano = Path(directorio) / "d.json"
            plano.write_text('[{"id":"a","prompt":"x"}]', encoding="utf-8")
            self.assertEqual(len(corrida.cargar_volcados(plano)), 1)

    def test_rechaza_dataset_vacio_o_inexistente(self) -> None:
        with TemporaryDirectory() as directorio:
            vacio = Path(directorio) / "vacio.json"
            vacio.write_text("[]", encoding="utf-8")
            with self.assertRaises(SystemExit):
                corrida.cargar_volcados(vacio)
            with self.assertRaises(SystemExit):
                corrida.cargar_volcados(Path(directorio) / "no-existe.jsonl")


class ContrasteTests(unittest.TestCase):
    """La comparación contra `esperado` es lo que evaluar.py no hace."""

    def test_reconoce_el_tipo_nombrado_en_el_reporte(self) -> None:
        esperado = {"ruteo": {"INC-x": {"tipo": "indisponibilidad"}}, "incidentes": 1}
        resultado = corrida.contrastar("El servicio sufre una indisponibilidad total.", esperado)
        self.assertEqual(resultado["tipos_esperados"], ["indisponibilidad"])
        self.assertEqual(resultado["tipos_nombrados"], ["indisponibilidad"])

    def test_no_inventa_coincidencias(self) -> None:
        esperado = {"ruteo": {"INC-x": {"tipo": "seguridad"}}}
        resultado = corrida.contrastar("Todo parece estar en orden.", esperado)
        self.assertEqual(resultado["tipos_nombrados"], [])

    def test_cuenta_las_secciones_del_reporte(self) -> None:
        texto = "Tipo de incidente\nCausa raíz\nEvidencia\nQué se descartó\nAcción correctiva"
        self.assertEqual(len(corrida.contrastar(texto, {})["secciones_presentes"]), 5)


class EjecucionTests(unittest.TestCase):
    def test_un_caso_mock_produce_reporte_completo(self) -> None:
        servicio = ChatService(MockProvider())
        caso = {"id": "x", "segment": "camino-feliz", "prompt": "Logs: 500 en /checkout", "esperado": {}}
        resultado = corrida.ejecutar_caso(servicio, caso)
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["modo"], "mock")

    def test_un_fallo_del_proveedor_no_revienta_la_corrida(self) -> None:
        class Roto:
            def stream(self, messages):
                raise ProviderError("el proveedor esta caido")

        resultado = corrida.ejecutar_caso(ChatService(Roto()), {"id": "y", "prompt": "hola"})
        self.assertFalse(resultado["ok"])
        self.assertIn("caido", resultado["error"])


class CategorizacionTests(unittest.TestCase):
    def test_cada_modulo_cae_en_su_categoria(self) -> None:
        for modulo, categoria in corrida.CATEGORIAS.items():
            with self.subTest(modulo=modulo):
                falso = type("T", (unittest.TestCase,), {})
                falso.__module__ = f"tests.{modulo}"
                self.assertEqual(corrida.categoria_de(falso("__init__")), categoria)

    def test_un_modulo_desconocido_no_se_pierde(self) -> None:
        falso = type("T", (unittest.TestCase,), {})
        falso.__module__ = "tests.test_algo_nuevo"
        self.assertEqual(corrida.categoria_de(falso("__init__")), corrida.CATEGORIA_POR_DEFECTO)


class AlmacenOpcionalTests(unittest.TestCase):
    def test_sin_credenciales_declara_y_no_asume_exito(self) -> None:
        config = Config(mode="mock", api_key=None, base_url="https://x", model="m")
        self.assertFalse(config.hay_almacen)
        self.assertEqual(corrida.verificar_almacen(config), 2)

    def test_guardar_sin_credenciales_no_revienta(self) -> None:
        config = Config(mode="mock", api_key=None, base_url="https://x", model="m")
        corrida.guardar_corrida(config, {"volcados": 0})  # no debe lanzar


if __name__ == "__main__":
    unittest.main()
