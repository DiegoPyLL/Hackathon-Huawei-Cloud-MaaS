"""Pruebas del emisor SARIF que alimenta la pestaña Security."""

import unittest

from src.maas_demo.orchestrator import TYPES
from src.maas_demo.sarif import NIVEL, PUNTAJE, construir_sarif


def corrida(*, origen="incidentes/uuid-1", linea=1, severidad="critica",
            tipo="seguridad", estado="completado"):
    return {
        "run_id": "corrida-1",
        "origen": origen,
        "linea": linea,
        "triage": {"incidentes": [{
            "id": "INC-01", "titulo": "Credencial expuesta", "tipo": tipo,
            "canal": "monitoreo", "severidad": severidad, "ataque_activo": True,
            "evidencia": ["10:41 acceso a 169.254.169.254"],
            "especialistas": ["secops"], "motivo_ruteo": "señal de seguridad",
        }]},
        "hallazgos": [{
            "incidente_id": "INC-01", "especialista": "secops", "estado": estado,
            "causa_raiz": "Token filtrado en el repositorio.", "confianza": "alta",
            "evidencia": ["commit a1b2c3 con la clave"], "descartado": ["fuerza bruta"],
            "viabilidad": "accionable",
        }],
    }


class EstructuraTests(unittest.TestCase):
    def test_declara_las_ocho_reglas_canonicas(self) -> None:
        reglas = construir_sarif([])["runs"][0]["tool"]["driver"]["rules"]
        self.assertEqual({r["id"] for r in reglas}, TYPES)

    def test_documento_valido_sin_corridas(self) -> None:
        documento = construir_sarif([])
        self.assertEqual(documento["version"], "2.1.0")
        self.assertEqual(documento["runs"][0]["results"], [])

    def test_un_resultado_por_hallazgo(self) -> None:
        resultados = construir_sarif([corrida(), corrida(origen="incidentes/uuid-2", linea=2)])
        self.assertEqual(len(resultados["runs"][0]["results"]), 2)

    def test_el_indice_de_regla_apunta_a_su_regla(self) -> None:
        documento = construir_sarif([corrida()])
        resultado = documento["runs"][0]["results"][0]
        reglas = documento["runs"][0]["tool"]["driver"]["rules"]
        self.assertEqual(reglas[resultado["ruleIndex"]]["id"], resultado["ruleId"])

    def test_ignora_un_hallazgo_sin_incidente(self) -> None:
        huerfana = corrida()
        huerfana["hallazgos"][0]["incidente_id"] = "INC-99"
        self.assertEqual(construir_sarif([huerfana])["runs"][0]["results"], [])


class SeveridadTests(unittest.TestCase):
    def test_mapea_cada_severidad_a_su_nivel_y_puntaje(self) -> None:
        for severidad in ("critica", "alta", "media", "baja"):
            with self.subTest(severidad=severidad):
                resultado = construir_sarif([corrida(severidad=severidad)])["runs"][0]["results"][0]
                self.assertEqual(resultado["level"], NIVEL[severidad])
                self.assertEqual(resultado["properties"]["security-severity"], PUNTAJE[severidad])


class MensajeTests(unittest.TestCase):
    def test_cita_la_evidencia_y_lo_descartado(self) -> None:
        texto = construir_sarif([corrida()])["runs"][0]["results"][0]["message"]["text"]
        self.assertIn("commit a1b2c3 con la clave", texto)
        self.assertIn("fuerza bruta", texto)
        self.assertIn("Token filtrado", texto)

    def test_un_hallazgo_fallido_declara_el_fallo(self) -> None:
        rota = corrida(estado="fallido")
        rota["hallazgos"][0]["error"] = "el especialista no devolvió JSON"
        texto = construir_sarif([rota])["runs"][0]["results"][0]["message"]["text"]
        self.assertIn("no devolvió JSON", texto)
        self.assertNotIn("Token filtrado", texto)


class HuellaTests(unittest.TestCase):
    def test_la_huella_es_estable_entre_corridas(self) -> None:
        primera = construir_sarif([corrida()])["runs"][0]["results"][0]
        segunda = corrida()
        segunda["run_id"] = "corrida-2"
        segunda = construir_sarif([segunda])["runs"][0]["results"][0]
        self.assertEqual(primera["partialFingerprints"], segunda["partialFingerprints"])

    def test_la_huella_distingue_origen_y_especialista(self) -> None:
        otra = corrida(origen="incidentes/uuid-2")
        self.assertNotEqual(
            construir_sarif([corrida()])["runs"][0]["results"][0]["partialFingerprints"],
            construir_sarif([otra])["runs"][0]["results"][0]["partialFingerprints"],
        )


class UbicacionTests(unittest.TestCase):
    def test_apunta_al_inventario_en_la_linea_del_volcado(self) -> None:
        ubicacion = construir_sarif([corrida(linea=7)])["runs"][0]["results"][0]["locations"][0]
        fisica = ubicacion["physicalLocation"]
        self.assertEqual(fisica["artifactLocation"]["uri"], "evals/results/incidentes-supabase.jsonl")
        self.assertEqual(fisica["region"]["startLine"], 7)


if __name__ == "__main__":
    unittest.main()
