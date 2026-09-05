"""La documentacion tiene que describir el sistema que existe.

Estas pruebas no revisan redaccion: revisan hechos comprobables contra el
codigo. Nacen de un caso concreto — al rebasar sobre main, sus documentos
describian el sistema de CINCO servicios y no mencionaban la pantalla de
trazabilidad (:8020), que `levantar_todo.py` ya levantaba. No hubo conflicto de
texto porque tocaban archivos distintos, y por eso mismo nadie se entero: un
merge limpio no significa un sistema coherente.
"""

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
LANZADOR = RAIZ / "projects" / "bus-incidentes" / "levantar_todo.py"
DEMO = RAIZ / "DEMO.md"
README = RAIZ / "README.md"


def puertos_que_levanta() -> set[str]:
    """Los puertos que el lanzador arranca de verdad, leidos de su tabla."""
    texto = LANZADOR.read_text(encoding="utf-8")
    bloque = texto[texto.index("SERVICIOS = ["):texto.index("def main()")]
    return set(re.findall(r'"--port",\s*"(\d+)"', bloque)) | set(
        re.findall(r"\],\s*(\d{4})\)", bloque))


class PuertosDocumentadosTests(unittest.TestCase):
    def setUp(self):
        self.puertos = puertos_que_levanta()

    def test_el_lanzador_declara_los_seis_servicios(self):
        self.assertEqual(len(self.puertos), 6, f"puertos hallados: {sorted(self.puertos)}")

    def test_demo_menciona_todos_los_puertos_que_se_levantan(self):
        texto = DEMO.read_text(encoding="utf-8")
        faltan = [p for p in sorted(self.puertos) if p not in texto]
        self.assertEqual(faltan, [], f"DEMO.md no menciona: {faltan}")

    def test_readme_menciona_todos_los_puertos_que_se_levantan(self):
        texto = README.read_text(encoding="utf-8")
        faltan = [p for p in sorted(self.puertos) if p not in texto]
        self.assertEqual(faltan, [], f"README.md no menciona: {faltan}")


class ValoresDocumentadosTests(unittest.TestCase):
    """Los numeros que la demo pide configurar tienen que ser los que el codigo
    usa. Un guion que dice 180 sobre un sistema calibrado a 280 hace fallar la
    demo de quien lo siga al pie de la letra."""

    def test_el_timeout_del_guion_coincide_con_el_ejemplo_de_entorno(self):
        demo = DEMO.read_text(encoding="utf-8")
        ejemplo = (RAIZ / ".env.example").read_text(encoding="utf-8")
        del_ejemplo = re.search(r"MAAS_TIMEOUT_SECONDS=(\d+)", ejemplo)
        self.assertIsNotNone(del_ejemplo, ".env.example no declara el timeout")
        valor = del_ejemplo.group(1)
        self.assertIn(f"MAAS_TIMEOUT_SECONDS={valor}", demo,
                      f"DEMO.md no usa el timeout del .env.example ({valor})")

    def test_el_presupuesto_del_guion_coincide_con_el_del_orquestador(self):
        from src.maas_demo.orchestrator import PRESUPUESTO_CORRIDA_SEG
        demo = DEMO.read_text(encoding="utf-8")
        self.assertIn(f"{int(PRESUPUESTO_CORRIDA_SEG)}s", demo,
                      "DEMO.md no menciona el presupuesto real de corrida")


class ComandosDocumentadosTests(unittest.TestCase):
    """Un comando documentado que no existe es peor que no documentarlo."""

    def test_los_scripts_que_el_readme_manda_correr_existen(self):
        texto = README.read_text(encoding="utf-8")
        citados = set(re.findall(r"(scripts/ejecutablesBase/[\w.-]+\.py)", texto))
        citados |= set(re.findall(r"(projects/[\w/-]+\.py)", texto))
        self.assertTrue(citados, "el README no cita ningun script")
        faltan = [c for c in sorted(citados) if not (RAIZ / c).exists()]
        self.assertEqual(faltan, [], f"el README cita scripts inexistentes: {faltan}")


if __name__ == "__main__":
    unittest.main()
