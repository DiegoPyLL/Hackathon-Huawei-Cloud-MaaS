"""Contratos compartidos entre piezas del repositorio.

La doctrina de `docs/architecture/contratos-agentes.md` está transcrita en varios
sitios a la vez: el generador de monitoreo, el orquestador y el bus. Este módulo
existe para que esas copias no puedan divergir en silencio.
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
GENERADOR_DIR = RAIZ / "projects" / "monitoreo" / "generator"
GENERADOR = GENERADOR_DIR / "generate_monitoreo_dumps.py"


def cargar_generador():
    spec = importlib.util.spec_from_file_location("generate_monitoreo_dumps", GENERADOR)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


gen = cargar_generador()

# Tercer testigo: la doctrina escrita a mano desde contratos-agentes.md, para que
# un cambio en el generador no se "auto-valide" comparandose consigo mismo.
TIPOS_CANONICOS = {
    "indisponibilidad",
    "degradacion",
    "error-funcional",
    "acceso-identidad",
    "datos",
    "integracion-terceros",
    "capacidad",
    "seguridad",
}
ESPECIALISTAS_CANONICOS = {"dba", "sysadmin", "secops"}
ACCIONES_CANONICAS = {
    "cerrar_alerta_falsa",
    "anotar_incidente",
    "bloquear_ip",
    "revocar_sesion",
    "forzar_reset_credencial",
    "deshabilitar_cuenta",
    "revocar_credencial_api",
    "aislar_host",
    "liberar_bloqueo_tabla",
    "revertir_deploy",
}

try:
    from src.maas_demo import orchestrator

    HAY_ORQUESTADOR = True
except ImportError:
    orchestrator = None
    HAY_ORQUESTADOR = False

SIN_ORQUESTADOR = "src/maas_demo/orchestrator.py aun no esta en main"


class ApiPublicaTests(unittest.TestCase):
    """Los nombres que otros proyectos importan no pueden desaparecer."""

    def test_los_nombres_declarados_existen(self) -> None:
        for nombre in gen.API_PUBLICA:
            with self.subTest(nombre=nombre):
                self.assertTrue(hasattr(gen, nombre), f"falta {nombre}, que otros importan")

    def test_el_bus_puede_importar_lo_que_usa(self) -> None:
        """Reproduce el import literal de projects/bus-incidentes/bus.py.

        Si alguien renombra o mueve el generador, falla aqui y no en el arranque
        del bus.
        """
        sys.path.insert(0, str(GENERADOR_DIR))
        try:
            from generate_monitoreo_dumps import (  # noqa: F401
                ESCENARIOS,
                RUTEO_DEFECTO,
                SERVICIOS,
                Ids,
            )
        finally:
            sys.path.remove(str(GENERADOR_DIR))

        self.assertTrue(SERVICIOS and ESCENARIOS and RUTEO_DEFECTO)
        self.assertTrue(callable(Ids))


class TaxonomiaCanonicaTests(unittest.TestCase):
    def test_los_ocho_tipos_coinciden_con_el_contrato(self) -> None:
        self.assertEqual(set(gen.TIPOS), TIPOS_CANONICOS)

    def test_especialistas_cerrados(self) -> None:
        self.assertEqual(gen.ESPECIALISTAS, ESPECIALISTAS_CANONICOS)

    def test_catalogo_de_acciones_cerrado(self) -> None:
        self.assertEqual(gen.ACCIONES, ACCIONES_CANONICAS)

    def test_cada_tipo_tiene_especialista_por_defecto(self) -> None:
        self.assertEqual(set(gen.RUTEO_DEFECTO), TIPOS_CANONICOS)
        for tipo, especialista in gen.RUTEO_DEFECTO.items():
            with self.subTest(tipo=tipo):
                self.assertIn(especialista, ESPECIALISTAS_CANONICOS)


@unittest.skipUnless(HAY_ORQUESTADOR, SIN_ORQUESTADOR)
class OrquestadorSinDerivaTests(unittest.TestCase):
    """El orquestador y el generador codifican la misma doctrina por separado.

    Estas comprobaciones estan en `skipped` hasta que orchestrator.py llegue a
    main; a partir de ahi exigen que las dos copias no se separen.
    """

    def test_tipos_no_divergen(self) -> None:
        self.assertEqual(set(orchestrator.TYPES), set(gen.TIPOS))

    def test_especialistas_no_divergen(self) -> None:
        self.assertEqual(set(orchestrator.SPECIALISTS), gen.ESPECIALISTAS)

    def test_catalogo_de_acciones_no_diverge(self) -> None:
        self.assertEqual(set(orchestrator.ACTION_CATALOG), gen.ACCIONES)

    def test_presupuesto_coincide_con_el_documentado(self) -> None:
        self.assertEqual(orchestrator.MAX_INCIDENTS, 6)
        self.assertEqual(orchestrator.MAX_SPECIALISTS, 2)


class EvalsSchemaTests(unittest.TestCase):
    """evaluar.py lee id/segment/prompt: si falta uno, revienta con KeyError."""

    def test_los_datasets_traen_las_claves_que_evaluar_exige(self) -> None:
        for nombre in ("cases.json", "casos-multi-incidente.json"):
            ruta = RAIZ / "evals" / nombre
            with self.subTest(dataset=nombre):
                casos = json.loads(ruta.read_text(encoding="utf-8"))
                self.assertIsInstance(casos, list)
                self.assertTrue(casos)
                for caso in casos:
                    for clave in ("id", "segment", "prompt"):
                        self.assertIn(clave, caso, f"{nombre}/{caso.get('id', '?')}")

    def test_los_identificadores_no_se_repiten(self) -> None:
        for nombre in ("cases.json", "casos-multi-incidente.json"):
            casos = json.loads((RAIZ / "evals" / nombre).read_text(encoding="utf-8"))
            ids = [caso["id"] for caso in casos]
            with self.subTest(dataset=nombre):
                self.assertEqual(len(ids), len(set(ids)))


class DatasetMonitoreoTests(unittest.TestCase):
    """El volcado versionado tambien alimenta a evaluar.py."""

    def setUp(self) -> None:
        ruta = RAIZ / "projects" / "monitoreo" / "data" / "monitoreo_dumps.jsonl"
        self.volcados = [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines()]

    def test_tiene_las_claves_que_evaluar_exige(self) -> None:
        for volcado in self.volcados:
            for clave in ("id", "segment", "prompt"):
                self.assertIn(clave, volcado)

    def test_cumple_el_contrato_del_generador(self) -> None:
        self.assertEqual(gen.validar(self.volcados), [])

    def test_cubre_los_ocho_tipos(self) -> None:
        tipos = {
            ruteo["tipo"]
            for volcado in self.volcados
            for ruteo in volcado["esperado"].get("ruteo", {}).values()
        }
        self.assertEqual(tipos, TIPOS_CANONICOS)


if __name__ == "__main__":
    unittest.main()
