"""Pruebas del puntuador multi-escenario (N-04).

Lo que se garantiza aqui es lo que hace util al numero: que una corrida fallida
no mejore la media por desaparecer de ella, y que el TOTAL se recalcule sobre
todos los incidentes en vez de promediar porcentajes de denominadores distintos.
"""

import importlib.util
import json
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


tz = cargar("trazabilidad", RAIZ / "projects" / "agente-puente" / "trazabilidad.py")
pt = cargar("puntuar", RAIZ / "scripts" / "ejecutablesBase" / "puntuar.py")

LINEA = "evento=deploy release=v360 deploy=DEP-404 componente=checkout by=ci-bot"


def verdad_con(ident="INC-01", tipo="indisponibilidad"):
    return {"incidentes": [{
        "incidente_id": ident, "escenario": "caida_tras_deploy", "tipo": tipo,
        "severidad": "alta", "servicio": "checkout", "panel_semaforo": "API Gateway",
        "ruteo_defecto": "sysadmin", "accion_esperada": None, "resuelto": False,
        "reportado_en": {"monitoreo": "t"},
        "lineas": [{"offset_seg": 0, "timestamp": "t", "texto": LINEA}],
    }]}


def triage_con(tipo="indisponibilidad"):
    return {"incidentes": [{
        "id": "INC-01", "titulo": "x", "tipo": tipo, "severidad": "alta",
        "especialistas": ["sysadmin"], "evidencia": [LINEA],
    }], "descartados": []}


class PuntuarCorridaTests(unittest.TestCase):
    def test_una_corrida_con_error_no_puntua(self):
        resultado = {"agente": {"error": "Huawei MaaS superó el plazo", "triage": None}}
        self.assertIsNone(pt.puntuar_corrida(resultado))

    def test_una_corrida_sin_triage_no_puntua(self):
        """Sin triage no hay nada que puntuar; devolver ceros seria inventar."""
        self.assertIsNone(pt.puntuar_corrida({"agente": {"triage": None}}))

    def test_una_corrida_buena_puntua(self):
        resultado = {
            "agente": {"triage": triage_con(), "hallazgos": []},
            "_verdad": verdad_con(),
            "_canales": {"monitoreo": [LINEA]},
        }
        p = pt.puntuar_corrida(resultado)
        self.assertEqual(p["recall"], 1.0)
        self.assertEqual(p["exactitud_tipo"], 1.0)


class TotalTests(unittest.TestCase):
    def test_el_total_se_recalcula_no_se_promedian_las_filas(self):
        """Dos corridas: una acierta el tipo sobre 1 incidente, otra falla sobre 3.

        Promediar las filas daria (100% + 0%)/2 = 50%. Recalcular sobre los 4
        incidentes da 25%, que es lo cierto.
        """
        linaje = []
        linaje += tz.construir_linaje(verdad_con("INC-01"), triage_con(), [],
                                      {"monitoreo": [LINEA]})
        for ident in ("INC-02", "INC-03", "INC-04"):
            linaje += tz.construir_linaje(
                verdad_con(ident), triage_con(tipo="degradacion"), [],
                {"monitoreo": [LINEA]})

        total = tz.puntuar(linaje, falsos_positivos=0)
        self.assertEqual(total["incidentes_reales"], 4)
        self.assertEqual(total["exactitud_tipo"], 0.25)
        self.assertNotEqual(total["exactitud_tipo"], 0.5, "no se promedian las filas")


class SalidaTests(unittest.TestCase):
    def test_la_tabla_marca_las_corridas_fallidas(self):
        import io, contextlib
        filas = [
            {"escenario": "caida_tras_deploy", "puntuacion": None,
             "motivo": "el triage no entrego nada"},
        ]
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            pt.imprimir_tabla(filas, None)
        texto = salida.getvalue()
        self.assertIn("CORRIDA FALLIDA", texto)
        self.assertIn("el triage no entrego nada", texto)

    def test_una_tasa_sin_universo_se_muestra_como_na(self):
        self.assertEqual(pt.formatear(None).strip(), "n/a")
        self.assertEqual(pt.formatear(1.0).strip(), "100%")


if __name__ == "__main__":
    unittest.main()


class PlazoDelPuenteTests(unittest.TestCase):
    """El puente tenia el mismo defecto que el provider: `urlopen(timeout=600)`
    sobre un stream SSE es un maximo ENTRE LECTURAS, no un plazo total.

    Sintoma medido: una corrida disparada desde :8020 quedo colgada con el
    agente sano y la cola de aprobaciones vacia. El hilo nunca solto su candado
    y la pantalla se quedo en "corriendo" indefinidamente.
    """

    def test_el_puente_declara_un_plazo_de_reloj_por_encima_del_presupuesto(self):
        puente = cargar("puente", RAIZ / "projects" / "agente-puente" / "puente.py")
        # La red de seguridad tiene que estar POR ENCIMA del presupuesto del
        # orquestador (300s): si estuviera por debajo, cortaria corridas sanas.
        self.assertGreater(puente.CORRIDA_MAX_SEG, 300.0)
        # Y el maximo entre lecturas, muy por debajo: un stream vivo manda algo
        # mucho antes de dos minutos.
        self.assertLess(puente.LECTURA_MAX_SEG, puente.CORRIDA_MAX_SEG)
