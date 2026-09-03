"""Pruebas del generador del canal monitoreo.

El generador ya trae `--autotest`; aqui se envuelve para que corra con la suite,
y se anaden las garantias que el autotest no cubre: determinismo, fidelidad del
dataset versionado y que el validador detecte de verdad cada violacion.
"""

import copy
import importlib.util
import json
import random
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
PROYECTO = RAIZ / "projects" / "monitoreo"
DATASET = PROYECTO / "data" / "monitoreo_dumps.jsonl"
SEMILLA_VERSIONADA = 7


def cargar_generador():
    ruta = PROYECTO / "generator" / "generate_monitoreo_dumps.py"
    spec = importlib.util.spec_from_file_location("generate_monitoreo_dumps", ruta)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


gen = cargar_generador()


def generar(semilla: int, n: int = 40) -> list[dict]:
    """Reproduce exactamente la secuencia de main(): un unico RNG compartido."""
    rng = random.Random(semilla)
    specs = gen.elegir_volcados(rng, n)
    return [
        gen.construir_volcado(
            rng,
            i,
            spec["segmento"],
            spec["escenarios"],
            spec["ruidos"],
            hostil=spec.get("hostil", False),
            presupuesto=spec.get("presupuesto", False),
        )
        for i, spec in enumerate(specs, start=1)
    ]


class AutotestTests(unittest.TestCase):
    def test_el_autotest_del_generador_pasa(self) -> None:
        self.assertEqual(gen.cmd_autotest(), 0)


class CatalogoTests(unittest.TestCase):
    def test_dos_escenarios_por_cada_tipo(self) -> None:
        por_tipo: dict[str, int] = {}
        for fn in gen.ESCENARIOS.values():
            escenario = fn(gen.Ids(random.Random(0)), random.Random(0))
            por_tipo[escenario["tipo"]] = por_tipo.get(escenario["tipo"], 0) + 1
        self.assertEqual(set(por_tipo), set(gen.TIPOS))
        self.assertTrue(all(cuenta == 2 for cuenta in por_tipo.values()), por_tipo)

    def test_cada_ruido_trae_el_dato_que_lo_descarta(self) -> None:
        for nombre, fn in gen.RUIDOS.items():
            with self.subTest(ruido=nombre):
                self.assertTrue(fn(gen.Ids(random.Random(0)), random.Random(0))["descartado"])


class DeterminismoTests(unittest.TestCase):
    def test_misma_semilla_mismo_resultado(self) -> None:
        self.assertEqual(generar(11), generar(11))

    def test_semillas_distintas_dan_datasets_distintos(self) -> None:
        self.assertNotEqual(generar(11), generar(12))


class DatasetVersionadoTests(unittest.TestCase):
    """El .jsonl del repo debe ser reproducible desde el generador.

    Falla tanto si alguien edita el dataset a mano como si cambia el generador
    sin regenerarlo.
    """

    def setUp(self) -> None:
        self.volcados = [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines()]

    def test_se_reproduce_con_la_semilla_declarada(self) -> None:
        self.assertEqual(generar(SEMILLA_VERSIONADA), self.volcados)

    def test_cumple_el_contrato(self) -> None:
        self.assertEqual(gen.validar(self.volcados), [])


class ValidadorTests(unittest.TestCase):
    """El validador tiene que fallar cuando debe, no solo pasar cuando todo va bien."""

    def setUp(self) -> None:
        self.base = [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines()]

    def _roto(self, romper):
        datos = copy.deepcopy(self.base)
        romper(next(v for v in datos if v["esperado"].get("ruteo")))
        return gen.validar(datos)

    def test_detecta_tipo_fuera_de_los_ocho(self) -> None:
        def romper(v):
            clave = list(v["esperado"]["ruteo"])[0]
            v["esperado"]["ruteo"][clave]["tipo"] = "otro"

        self.assertTrue(any("fuera de los 8" in e for e in self._roto(romper)))

    def test_detecta_especialista_invalido(self) -> None:
        def romper(v):
            list(v["esperado"]["ruteo"].values())[0]["especialistas"] = ["devops"]

        self.assertTrue(any("invalido" in e for e in self._roto(romper)))

    def test_detecta_mas_de_dos_especialistas(self) -> None:
        def romper(v):
            list(v["esperado"]["ruteo"].values())[0]["especialistas"] = [
                "dba",
                "secops",
                "sysadmin",
            ]

        self.assertTrue(any("1..2" in e for e in self._roto(romper)))

    def test_detecta_ruteo_sin_el_especialista_por_defecto(self) -> None:
        def romper(v):
            ruteo = list(v["esperado"]["ruteo"].values())[0]
            defecto = gen.RUTEO_DEFECTO[ruteo["tipo"]]
            ruteo["especialistas"] = [e for e in gen.ESPECIALISTAS if e != defecto][:1]

        self.assertTrue(any("por defecto" in e for e in self._roto(romper)))

    def test_detecta_accion_fuera_del_catalogo(self) -> None:
        def romper(v):
            v["esperado"]["acciones_esperadas"] = [
                {
                    "incidente": list(v["esperado"]["ruteo"])[0],
                    "action_id": "reiniciar_servidor",
                    "params_clave": {},
                }
            ]

        self.assertTrue(any("catalogo cerrado" in e for e in self._roto(romper)))

    def test_detecta_accion_sobre_incidente_inexistente(self) -> None:
        def romper(v):
            v["esperado"]["acciones_esperadas"] = [
                {"incidente": "INC-no-existe", "action_id": "bloquear_ip", "params_clave": {}}
            ]

        self.assertTrue(any("no esta en el ruteo" in e for e in self._roto(romper)))

    def test_detecta_identificador_malformado(self) -> None:
        def romper(v):
            v["prompt"] = v["prompt"].replace("ALRT-", "ALRT-XX", 1)

        self.assertTrue(any("no cumple el patron" in e for e in self._roto(romper)))

    def test_detecta_tipo_sin_cobertura(self) -> None:
        sin_seguridad = [
            v for v in self.base if "seguridad" not in json.dumps(v["esperado"])
        ]
        self.assertTrue(any("sin ningun caso" in e for e in gen.validar(sin_seguridad)))
        # el mismo subconjunto es valido si no se exige cobertura
        self.assertEqual(
            [e for e in gen.validar(sin_seguridad, exigir_cobertura=False) if "sin ningun caso" in e],
            [],
        )

    def test_acepta_el_fragmento_truncado_deliberado(self) -> None:
        datos = copy.deepcopy(self.base)
        datos[0]["prompt"] += " | ... alert=ALRT-77?? ilegible ..."
        self.assertEqual(gen.validar(datos), [])


class PresupuestoTests(unittest.TestCase):
    def test_el_segmento_de_tope_respeta_el_maximo(self) -> None:
        volcados = [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines()]
        topes = [v for v in volcados if v["segment"] == "tope-presupuesto"]
        self.assertTrue(topes, "el dataset deberia incluir el segmento tope-presupuesto")
        for volcado in topes:
            esperado = volcado["esperado"]
            with self.subTest(volcado=volcado["id"]):
                self.assertEqual(esperado["incidentes_analizados"], 6)
                self.assertGreater(esperado["incidentes_detectados"], 6)
                self.assertEqual(
                    esperado["diferidos"],
                    esperado["incidentes_detectados"] - esperado["incidentes_analizados"],
                )
                self.assertTrue(esperado["diferidos_esperados"])


if __name__ == "__main__":
    unittest.main()
