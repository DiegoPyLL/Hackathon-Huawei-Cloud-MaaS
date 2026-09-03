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


class VolcadosSupabaseTests(unittest.TestCase):
    """La lectura del almacén no puede inventar volcados ni perder filas."""

    def _config(self, con_almacen=True):
        return Config(
            mode="mock", api_key=None, base_url="https://x", model="m",
            supabase_url="https://p.supabase.co" if con_almacen else None,
            supabase_key="service-role-de-prueba" if con_almacen else None,
        )

    def _con_tablas(self, tablas):
        class AlmacenFalso:
            def __init__(self, **kwargs):
                pass

            def consultar_todo(self, tabla, **kwargs):
                return tablas[tabla]

        return mock.patch.object(corrida, "Almacen", AlmacenFalso)

    def test_sin_credenciales_no_inventa_una_corrida(self) -> None:
        with self.assertRaises(SystemExit):
            corrida.volcados_desde_supabase(self._config(con_almacen=False))

    def test_convierte_incidentes_y_correos_con_su_canal(self) -> None:
        tablas = {
            "incidentes": [{"id": "u1", "ticket_numero": "INC-0001", "titulo": "Checkout caido",
                            "descripcion": "responde 503", "sistema_afectado": "checkout-api",
                            "severidad": "alta", "logs_adjuntos": ["10:15 503 GET /checkout"]}],
            "emails_entrantes": [{"id": "u2", "message_id": "<a@b>", "remitente": "cliente@x.com",
                                  "asunto": "No puedo pagar", "cuerpo": "me sale error"}],
        }
        with self._con_tablas(tablas):
            volcados = corrida.volcados_desde_supabase(self._config())

        self.assertEqual([v["canal"] for v in volcados], ["monitoreo", "email-soporte"])
        self.assertEqual([v["origen"] for v in volcados], ["incidentes/u1", "emails_entrantes/u2"])
        self.assertIn("10:15 503 GET /checkout", volcados[0]["prompt"])
        self.assertIn("me sale error", volcados[1]["prompt"])

    def test_descarta_filas_sin_contenido(self) -> None:
        tablas = {
            "incidentes": [{"id": "u1", "titulo": "", "descripcion": "", "logs_adjuntos": []}],
            "emails_entrantes": [{"id": "u2", "remitente": "a@b", "asunto": "", "cuerpo": ""}],
        }
        with self._con_tablas(tablas):
            self.assertEqual(corrida.volcados_desde_supabase(self._config()), [])

    def test_una_tabla_ilegible_no_aborta_la_otra(self) -> None:
        class AlmacenParcial:
            def __init__(self, **kwargs):
                pass

            def consultar_todo(self, tabla, **kwargs):
                if tabla == "incidentes":
                    raise corrida.AlmacenError("tabla inaccesible")
                return [{"id": "u2", "asunto": "hola", "cuerpo": "algo", "remitente": "a@b"}]

        with mock.patch.object(corrida, "Almacen", AlmacenParcial):
            volcados = corrida.volcados_desde_supabase(self._config())
        self.assertEqual(len(volcados), 1)


class InventarioTests(unittest.TestCase):
    def test_escribe_una_linea_por_volcado(self) -> None:
        with TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "sub" / "inventario.jsonl"
            corrida.escribir_inventario([{"id": "a"}, {"id": "b"}], ruta)
            lineas = ruta.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual([json.loads(l)["id"] for l in lineas], ["a", "b"])


class OrquestarTests(unittest.TestCase):
    """El flujo multiagente real, en mock: sin red y determinista."""

    def _config(self):
        return Config(mode="mock", api_key=None, base_url="https://x", model="m")

    def _volcado(self, indice):
        return {"id": f"v{indice}", "origen": f"incidentes/u{indice}", "canal": "monitoreo",
                "prompt": "10:15 cpu.pct=97 conn.active=980 y 503 GET /checkout"}

    def test_devuelve_una_corrida_por_volcado_con_su_linea(self) -> None:
        corridas, pendientes = corrida.orquestar(self._config(), [self._volcado(1), self._volcado(2)], 0)
        self.assertEqual(pendientes, [])
        self.assertEqual([c["linea"] for c in corridas], [1, 2])
        self.assertEqual([c["origen"] for c in corridas], ["incidentes/u1", "incidentes/u2"])
        self.assertTrue(corridas[0]["hallazgos"])

    def test_el_presupuesto_agotado_declara_lo_pendiente(self) -> None:
        # Reloj falso: el presupuesto ya venció cuando se mira el primer volcado.
        with mock.patch.object(corrida.time, "monotonic", side_effect=[0.0, 10_000.0]):
            corridas, pendientes = corrida.orquestar(
                self._config(), [self._volcado(1), self._volcado(2)], 5
            )
        self.assertEqual(corridas, [])
        self.assertEqual([v["origen"] for v in pendientes], ["incidentes/u1", "incidentes/u2"])

    def test_sin_presupuesto_no_corta(self) -> None:
        corridas, pendientes = corrida.orquestar(self._config(), [self._volcado(1)], 0)
        self.assertEqual(len(corridas), 1)
        self.assertEqual(pendientes, [])

    def test_un_volcado_invalido_no_aborta_el_resto(self) -> None:
        roto = {"id": "roto", "origen": "incidentes/u0", "canal": "monitoreo", "prompt": "   "}
        corridas, _ = corrida.orquestar(self._config(), [roto, self._volcado(1)], 0)
        self.assertEqual(len(corridas), 1)
        self.assertEqual(corridas[0]["origen"], "incidentes/u1")


class SarifSalidaTests(unittest.TestCase):
    def test_escribe_el_documento_y_cuenta_las_alertas(self) -> None:
        config = Config(mode="mock", api_key=None, base_url="https://x", model="m")
        corridas, _ = corrida.orquestar(
            config,
            [{"id": "v1", "origen": "incidentes/u1", "canal": "monitoreo",
              "prompt": "10:15 cpu.pct=97 y 503 GET /checkout"}],
            0,
        )
        with TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "out" / "incidentes.sarif"
            total = corrida.escribir_sarif(corridas, ruta)
            documento = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertEqual(total, len(documento["runs"][0]["results"]))
        self.assertGreater(total, 0)
        self.assertEqual(documento["version"], "2.1.0")


if __name__ == "__main__":
    unittest.main()
