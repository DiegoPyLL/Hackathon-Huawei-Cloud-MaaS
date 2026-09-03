"""Pruebas del cliente de Supabase, sin tocar la base real.

El `opener` inyectable permite ejercitar el camino completo (cabeceras, códigos
de error, parseo) sin red, igual que hace `test_provider.py` con MaaSProvider.
"""

import json
import unittest
import urllib.error
from unittest import mock

from src.maas_demo.almacen import TABLAS, Almacen, AlmacenError
from src.maas_demo.config import Config


KEY = "service-role-de-prueba-no-real"


class RespuestaFalsa:
    def __init__(self, cuerpo=b"[]", cabeceras=None):
        self._cuerpo = cuerpo
        self.headers = cabeceras or {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self):
        return self._cuerpo


def opener_que_captura(peticiones, respuesta=None):
    def opener(request, timeout=None):
        peticiones.append(request)
        return respuesta if respuesta is not None else RespuestaFalsa()

    return opener


def opener_que_falla(codigo):
    def opener(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, codigo, "nope", {}, None)

    return opener


class ConstruccionTests(unittest.TestCase):
    def test_exige_ambas_credenciales(self) -> None:
        with self.assertRaisesRegex(AlmacenError, "SUPABASE_URL"):
            Almacen(url="", service_key=KEY)
        with self.assertRaisesRegex(AlmacenError, "SUPABASE_SERVICE_ROLE_KEY"):
            Almacen(url="https://x.supabase.co", service_key="")

    def test_rest_url_no_se_duplica(self) -> None:
        self.assertEqual(
            Almacen(url="https://x.supabase.co", service_key=KEY).rest_url,
            "https://x.supabase.co/rest/v1",
        )
        self.assertEqual(
            Almacen(url="https://x.supabase.co/rest/v1/", service_key=KEY).rest_url,
            "https://x.supabase.co/rest/v1",
        )

    def test_desde_entorno_declara_lo_que_falta(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(AlmacenError, "SUPABASE_URL"):
                Almacen.desde_entorno()


class CabecerasTests(unittest.TestCase):
    def test_envia_apikey_y_bearer(self) -> None:
        peticiones = []
        almacen = Almacen(
            url="https://x.supabase.co", service_key=KEY, opener=opener_que_captura(peticiones)
        )
        almacen.consultar("incidentes")

        enviada = peticiones[0]
        self.assertEqual(enviada.get_header("Apikey"), KEY)
        self.assertEqual(enviada.get_header("Authorization"), f"Bearer {KEY}")
        self.assertIn("/rest/v1/incidentes", enviada.full_url)

    def test_insertar_pide_la_fila_de_vuelta(self) -> None:
        peticiones = []
        almacen = Almacen(
            url="https://x.supabase.co",
            service_key=KEY,
            opener=opener_que_captura(peticiones, RespuestaFalsa(b'[{"id":1}]')),
        )
        filas = almacen.insertar("incidentes", {"titulo": "prueba"})

        self.assertEqual(filas, [{"id": 1}])
        enviada = peticiones[0]
        self.assertEqual(enviada.method, "POST")
        self.assertEqual(enviada.get_header("Prefer"), "return=representation")
        self.assertEqual(json.loads(enviada.data), {"titulo": "prueba"})


class ErroresTests(unittest.TestCase):
    def test_la_credencial_nunca_aparece_en_un_error(self) -> None:
        """Regla de AGENTS.md: la key no se imprime, ni siquiera al fallar."""
        for codigo in (401, 403, 404, 500):
            almacen = Almacen(
                url="https://x.supabase.co", service_key=KEY, opener=opener_que_falla(codigo)
            )
            with self.subTest(codigo=codigo):
                with self.assertRaises(AlmacenError) as capturado:
                    almacen.consultar("incidentes")
                self.assertNotIn(KEY, str(capturado.exception))

    def test_401_apunta_a_la_variable_correcta(self) -> None:
        almacen = Almacen(
            url="https://x.supabase.co", service_key=KEY, opener=opener_que_falla(401)
        )
        with self.assertRaisesRegex(AlmacenError, "SUPABASE_SERVICE_ROLE_KEY"):
            almacen.consultar("incidentes")

    def test_sin_red_falla_declarando(self) -> None:
        def opener(request, timeout=None):
            raise urllib.error.URLError("sin ruta al host")

        almacen = Almacen(url="https://x.supabase.co", service_key=KEY, opener=opener)
        with self.assertRaisesRegex(AlmacenError, "No se pudo conectar"):
            almacen.consultar("incidentes")

    def test_respuesta_no_json_se_declara(self) -> None:
        almacen = Almacen(
            url="https://x.supabase.co",
            service_key=KEY,
            opener=opener_que_captura([], RespuestaFalsa(b"<html>502</html>")),
        )
        with self.assertRaisesRegex(AlmacenError, "no es JSON"):
            almacen.consultar("incidentes")


class ConteoTests(unittest.TestCase):
    def test_contar_lee_content_range(self) -> None:
        almacen = Almacen(
            url="https://x.supabase.co",
            service_key=KEY,
            opener=opener_que_captura([], RespuestaFalsa(b"", {"Content-Range": "0-0/42"})),
        )
        self.assertEqual(almacen.contar("incidentes"), 42)

    def test_tabla_vacia_cuenta_cero(self) -> None:
        almacen = Almacen(
            url="https://x.supabase.co",
            service_key=KEY,
            opener=opener_que_captura([], RespuestaFalsa(b"", {"Content-Range": "*/0"})),
        )
        self.assertEqual(almacen.contar("incidentes"), 0)

    def test_verificar_cubre_las_tablas_del_esquema(self) -> None:
        almacen = Almacen(
            url="https://x.supabase.co",
            service_key=KEY,
            opener=opener_que_captura([], RespuestaFalsa(b"", {"Content-Range": "0-0/7"})),
        )
        conteos = almacen.verificar()
        self.assertEqual(set(conteos), set(TABLAS))
        self.assertEqual(conteos["incidentes"], 7)

    def test_verificar_no_revienta_si_una_tabla_falla(self) -> None:
        almacen = Almacen(
            url="https://x.supabase.co", service_key=KEY, opener=opener_que_falla(404)
        )
        conteos = almacen.verificar()
        self.assertTrue(all(str(v).startswith("error:") for v in conteos.values()))
        self.assertTrue(all(KEY not in str(v) for v in conteos.values()))


class PaginacionTests(unittest.TestCase):
    """`consultar_todo` no puede confiar en una sola llamada: PostgREST corta."""

    def _almacen_con_paginas(self, paginas):
        self.peticiones = []

        def opener(request, timeout=None):
            self.peticiones.append(request.full_url)
            filas = paginas.pop(0) if paginas else []
            return RespuestaFalsa(json.dumps(filas).encode("utf-8"))

        return Almacen(url="https://p.supabase.co", service_key=KEY, opener=opener)

    def test_pide_paginas_hasta_una_incompleta(self) -> None:
        almacen = self._almacen_con_paginas([
            [{"id": i} for i in range(3)],
            [{"id": 3}],
        ])
        filas = almacen.consultar_todo("incidentes", pagina=3)
        self.assertEqual(len(filas), 4)
        self.assertEqual(len(self.peticiones), 2)
        self.assertIn("offset=0", self.peticiones[0])
        self.assertIn("offset=3", self.peticiones[1])

    def test_una_pagina_incompleta_no_pide_otra(self) -> None:
        almacen = self._almacen_con_paginas([[{"id": 0}]])
        self.assertEqual(len(almacen.consultar_todo("incidentes", pagina=100)), 1)
        self.assertEqual(len(self.peticiones), 1)

    def test_tabla_vacia_devuelve_lista_vacia(self) -> None:
        almacen = self._almacen_con_paginas([[]])
        self.assertEqual(almacen.consultar_todo("incidentes"), [])

    def test_consultar_acepta_desplazamiento(self) -> None:
        almacen = self._almacen_con_paginas([[]])
        almacen.consultar("incidentes", limite=5, desplazamiento=10)
        self.assertIn("limit=5", self.peticiones[0])
        self.assertIn("offset=10", self.peticiones[0])


class ConfigAlmacenTests(unittest.TestCase):
    def test_supabase_url_debe_ser_https(self) -> None:
        with mock.patch.dict("os.environ", {"SUPABASE_URL": "http://inseguro"}, clear=True):
            with self.assertRaisesRegex(Exception, "SUPABASE_URL"):
                Config.from_env()

    def test_hay_almacen_exige_las_dos_variables(self) -> None:
        entorno = {"SUPABASE_URL": "https://x.supabase.co"}
        with mock.patch.dict("os.environ", entorno, clear=True):
            self.assertFalse(Config.from_env().hay_almacen)
        with mock.patch.dict(
            "os.environ", {**entorno, "SUPABASE_SERVICE_ROLE_KEY": KEY}, clear=True
        ):
            self.assertTrue(Config.from_env().hay_almacen)


if __name__ == "__main__":
    unittest.main()
