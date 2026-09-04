"""Pruebas de la trazabilidad de punta a punta.

Lo que se garantiza aqui es la propiedad de la que cuelga todo lo demas: la
atribucion de un incidente detectado al incidente real se hace por la EVIDENCIA
citada, no por el tipo. Si eso se rompe, el embudo miente y el marcador tambien.
"""

import importlib.util
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


def cargar_trazabilidad():
    ruta = RAIZ / "projects" / "agente-puente" / "trazabilidad.py"
    spec = importlib.util.spec_from_file_location("trazabilidad", ruta)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


tz = cargar_trazabilidad()


LINEA_DEPLOY = "evento=deploy release=v360 deploy=DEP-404 componente=checkout by=ci-bot"
LINEA_500 = "alert=ALRT-9683 endpoint=/checkout status=500 ratio=0.90 ventana=2min"
LINEA_LOCK = "alert=ALRT-9101 metric=db.lock_wait_seconds value=487 tabla=pedidos trx=TRX-4471"


def verdad_de(*incidentes):
    return {"incidentes": list(incidentes), "activos": len(incidentes)}


def incidente(
    ident="INC-01", tipo="indisponibilidad", severidad="alta", servicio="checkout",
    lineas=(LINEA_DEPLOY, LINEA_500), reportado=("monitoreo",), accion=None,
    ruteo="sysadmin", resuelto=False,
):
    return {
        "incidente_id": ident,
        "escenario": "caida_tras_deploy",
        "tipo": tipo,
        "severidad": severidad,
        "servicio": servicio,
        "panel_semaforo": "API Gateway",
        "ruteo_defecto": ruteo,
        "accion_esperada": accion,
        "resuelto": resuelto,
        "reportado_en": {canal: "2026-09-04T00:00:00" for canal in reportado},
        "lineas": [{"offset_seg": i, "timestamp": "2026-09-04T00:00:0%d" % i, "texto": t}
                   for i, t in enumerate(lineas)],
    }


class IndiceDeLineasTest(unittest.TestCase):
    def test_atribuye_la_linea_a_su_incidente(self):
        indice = tz.IndiceDeLineas(verdad_de(incidente()))
        self.assertEqual(indice.atribuir(LINEA_DEPLOY), "INC-01")

    def test_atribuye_aunque_el_canal_le_ponga_prefijo(self):
        """El feed publica 'MONITOREO 00:26:04 <texto>' y los logs '00:26:04 ERROR
        <texto>'. Si el prefijo rompiera la atribucion, todo anclaria a None."""
        indice = tz.IndiceDeLineas(verdad_de(incidente()))
        self.assertEqual(indice.atribuir(f"MONITOREO 00:26:04 {LINEA_DEPLOY}"), "INC-01")
        self.assertEqual(indice.atribuir(f"00:26:04 ERROR {LINEA_500}"), "INC-01")

    def test_distingue_entre_dos_incidentes(self):
        indice = tz.IndiceDeLineas(verdad_de(
            incidente("INC-01"),
            incidente("INC-02", tipo="datos", lineas=(LINEA_LOCK,)),
        ))
        self.assertEqual(indice.atribuir(LINEA_DEPLOY), "INC-01")
        self.assertEqual(indice.atribuir(LINEA_LOCK), "INC-02")

    def test_una_cita_corta_no_ancla(self):
        """'value=0' aparece en medio repositorio: por debajo del umbral no se
        atribuye nada, porque una atribucion equivocada es peor que ninguna."""
        indice = tz.IndiceDeLineas(verdad_de(incidente()))
        self.assertIsNone(indice.atribuir("status=500"))

    def test_una_cita_inventada_no_ancla(self):
        indice = tz.IndiceDeLineas(verdad_de(incidente()))
        self.assertIsNone(indice.atribuir("alert=ALRT-0000 el servicio explotó sin motivo aparente"))


class AtribuirDeteccionTest(unittest.TestCase):
    def test_una_deteccion_con_evidencia_real_se_ancla(self):
        indice = tz.IndiceDeLineas(verdad_de(incidente()))
        atribucion = tz.atribuir_deteccion(
            {"id": "INC-01", "evidencia": [LINEA_DEPLOY, LINEA_500]}, indice)
        self.assertEqual(atribucion["incidente_real"], "INC-01")
        self.assertFalse(atribucion["falso_positivo"])
        self.assertEqual(len(atribucion["citas_ancladas"]), 2)

    def test_una_deteccion_sin_evidencia_real_es_falso_positivo(self):
        indice = tz.IndiceDeLineas(verdad_de(incidente()))
        atribucion = tz.atribuir_deteccion(
            {"id": "INC-09", "evidencia": ["el sistema se comporta de forma anómala y preocupante"]},
            indice)
        self.assertIsNone(atribucion["incidente_real"])
        self.assertTrue(atribucion["falso_positivo"])

    def test_gana_el_incidente_mas_citado(self):
        indice = tz.IndiceDeLineas(verdad_de(
            incidente("INC-01"),
            incidente("INC-02", lineas=(LINEA_LOCK,)),
        ))
        atribucion = tz.atribuir_deteccion(
            {"id": "INC-A", "evidencia": [LINEA_DEPLOY, LINEA_500, LINEA_LOCK]}, indice)
        self.assertEqual(atribucion["incidente_real"], "INC-01")

    def test_el_id_del_agente_no_manda_sobre_la_evidencia(self):
        """El agente numera sus incidentes INC-01, INC-02... y el bus tambien.
        Los ids CHOCAN y no significan lo mismo. La atribucion tiene que salir de
        la evidencia o el linaje quedaria cruzado."""
        indice = tz.IndiceDeLineas(verdad_de(
            incidente("INC-01"),
            incidente("INC-02", lineas=(LINEA_LOCK,)),
        ))
        atribucion = tz.atribuir_deteccion(
            {"id": "INC-01", "evidencia": [LINEA_LOCK]}, indice)
        self.assertEqual(atribucion["incidente_real"], "INC-02")


class LinajeTest(unittest.TestCase):
    def setUp(self):
        self.verdad = verdad_de(incidente(
            accion={"action_id": "revertir_deploy", "params_clave": {"deploy_id": "DEP-404"}}))
        self.canales = {"monitoreo": [f"MONITOREO 00:00:00 {LINEA_DEPLOY}",
                                      f"MONITOREO 00:00:01 {LINEA_500}"]}

    def test_incidente_no_detectado(self):
        [fila] = tz.construir_linaje(self.verdad, {"incidentes": []}, [], self.canales)
        self.assertFalse(fila["detectado"])
        self.assertEqual(fila["perdido_en"], "triage")

    def test_incidente_detectado_y_diagnosticado(self):
        triage = {"incidentes": [{
            "id": "INC-01", "titulo": "Caída de checkout", "tipo": "indisponibilidad",
            "severidad": "alta", "especialistas": ["sysadmin"],
            "evidencia": [LINEA_DEPLOY, LINEA_500],
        }]}
        hallazgos = [{
            "incidente_id": "INC-01", "especialista": "sysadmin", "estado": "completado",
            "causa_raiz": "El deploy DEP-404 rompió checkout.", "confianza": "alta",
            "accion": {"action_id": "revertir_deploy", "params": {"deploy_id": "DEP-404"}},
        }]
        [fila] = tz.construir_linaje(self.verdad, triage, hallazgos, self.canales)
        self.assertTrue(fila["detectado"])
        self.assertTrue(fila["tipo_correcto"])
        self.assertTrue(fila["severidad_correcta"])
        self.assertTrue(fila["ruteo_correcto"])
        self.assertTrue(fila["diagnosticado"])
        self.assertTrue(fila["accion_correcta"])
        self.assertIsNone(fila["perdido_en"])
        self.assertEqual(fila["lineas_en_volcado"], 2)

    def test_tipo_equivocado_se_declara(self):
        triage = {"incidentes": [{
            "id": "INC-01", "titulo": "x", "tipo": "degradacion", "severidad": "alta",
            "especialistas": ["sysadmin"], "evidencia": [LINEA_DEPLOY],
        }]}
        [fila] = tz.construir_linaje(self.verdad, triage, [], self.canales)
        self.assertTrue(fila["detectado"])
        self.assertFalse(fila["tipo_correcto"])
        self.assertEqual(fila["tipo_agente"], "degradacion")

    def test_accion_con_identificador_inventado_no_cuenta_como_correcta(self):
        triage = {"incidentes": [{
            "id": "INC-01", "titulo": "x", "tipo": "indisponibilidad", "severidad": "alta",
            "especialistas": ["sysadmin"], "evidencia": [LINEA_DEPLOY],
        }]}
        hallazgos = [{
            "incidente_id": "INC-01", "especialista": "sysadmin", "estado": "completado",
            "causa_raiz": "x", "confianza": "alta",
            "accion": {"action_id": "revertir_deploy", "params": {"deploy_id": "DEP-999"}},
        }]
        [fila] = tz.construir_linaje(self.verdad, triage, hallazgos, self.canales)
        self.assertFalse(fila["accion_correcta"])

    def test_los_resueltos_no_entran_al_linaje(self):
        verdad = verdad_de(incidente(resuelto=True))
        self.assertEqual(tz.construir_linaje(verdad, None, [], {}), [])

    def test_sin_lineas_en_el_volcado_se_pierde_en_recoleccion(self):
        [fila] = tz.construir_linaje(self.verdad, None, [], {"monitoreo": []})
        self.assertEqual(fila["perdido_en"], "recoleccion")


class EmbudoTest(unittest.TestCase):
    def test_las_etapas_no_crecen_hacia_abajo(self):
        verdad = verdad_de(
            incidente("INC-01"),
            incidente("INC-02", lineas=(LINEA_LOCK,), tipo="datos", ruteo="dba"),
        )
        triage = {"incidentes": [{
            "id": "INC-A", "titulo": "x", "tipo": "indisponibilidad", "severidad": "alta",
            "especialistas": ["sysadmin"], "evidencia": [LINEA_DEPLOY],
        }]}
        canales = {"monitoreo": [LINEA_DEPLOY, LINEA_500, LINEA_LOCK]}
        linaje = tz.construir_linaje(verdad, triage, [], canales)
        embudo = tz.construir_embudo(linaje)
        cantidades = [e["cantidad"] for e in embudo["etapas"]]
        self.assertEqual(cantidades, sorted(cantidades, reverse=True))
        self.assertEqual(embudo["total"], 2)

    def test_declara_donde_se_pierde_cada_uno(self):
        verdad = verdad_de(incidente("INC-01"), incidente("INC-02", lineas=(LINEA_LOCK,)))
        canales = {"monitoreo": [LINEA_DEPLOY, LINEA_500, LINEA_LOCK]}
        linaje = tz.construir_linaje(verdad, {"incidentes": []}, [], canales)
        embudo = tz.construir_embudo(linaje)
        self.assertEqual(embudo["perdidas_por_salto"], {"triage": 2})

    def test_embudo_vacio_no_divide_por_cero(self):
        embudo = tz.construir_embudo([])
        self.assertEqual(embudo["total"], 0)
        self.assertEqual(embudo["conversion_global"], 0.0)


class RuidoTest(unittest.TestCase):
    def test_cuenta_los_falsos_positivos(self):
        verdad = verdad_de(incidente())
        triage = {"incidentes": [
            {"id": "INC-01", "evidencia": [LINEA_DEPLOY]},
            {"id": "INC-02", "evidencia": ["algo raro pasó en algún lugar del sistema"]},
        ], "descartados": [{"senal": "x", "motivo": "y"}]}
        ruido = tz.construir_ruido(verdad, triage, {"monitoreo": [LINEA_DEPLOY]})
        self.assertEqual(ruido["falsos_positivos"], 1)
        self.assertEqual(ruido["detecciones_totales"], 2)
        self.assertEqual(ruido["precision"], 0.5)
        self.assertEqual(ruido["descartes_declarados"], 1)


class PorPantallaTest(unittest.TestCase):
    def test_declara_lo_que_cada_canal_no_publico(self):
        """Que un canal no reporte un incidente es informacion, no un fallo: la
        asimetria entre canales es deliberada."""
        verdad = verdad_de(
            incidente("INC-01", reportado=("monitoreo", "dev-chat")),
            incidente("INC-02", reportado=("monitoreo",)),
        )
        filas = {f["canal"]: f for f in tz.construir_por_pantalla(verdad, {"monitoreo": ["x"]})}
        self.assertEqual(filas["monitoreo"]["incidentes_publicados"], ["INC-01", "INC-02"])
        self.assertEqual(filas["dev-chat"]["incidentes_publicados"], ["INC-01"])
        self.assertEqual(filas["dev-chat"]["incidentes_no_publicados"], ["INC-02"])
        self.assertEqual(filas["monitoreo"]["cobertura"], 1.0)
        self.assertEqual(filas["dev-chat"]["cobertura"], 0.5)

    def test_un_canal_caido_se_declara_no_disponible(self):
        filas = {f["canal"]: f for f in tz.construir_por_pantalla(
            verdad_de(incidente()), {"monitoreo": ["x"], "logs": None})}
        self.assertTrue(filas["monitoreo"]["disponible"])
        self.assertFalse(filas["logs"]["disponible"])


class TrazarTest(unittest.TestCase):
    def test_el_informe_completo_trae_las_cuatro_partes(self):
        informe = tz.trazar(verdad_de(incidente()), {"monitoreo": [LINEA_DEPLOY]}, {})
        for clave in ("linaje", "embudo", "ruido", "por_pantalla"):
            self.assertIn(clave, informe)

    def test_sin_corrida_del_agente_sigue_habiendo_trazabilidad(self):
        """La pantalla tiene que servir antes de la primera corrida: la mitad
        izquierda del embudo (que se emitio y que se recogio) ya es util."""
        informe = tz.trazar(verdad_de(incidente()), {"monitoreo": [LINEA_DEPLOY]}, {})
        self.assertEqual(informe["embudo"]["total"], 1)
        self.assertEqual(informe["embudo"]["etapas"][0]["cantidad"], 1)
        self.assertEqual(informe["linaje"][0]["perdido_en"], "triage")


if __name__ == "__main__":
    unittest.main()
