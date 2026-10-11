"""
Pruebas de los servicios del worker: limpieza, IA (modo simulado) y validación.
Corre con: python manage.py test apps.transformaciones.tests_worker
"""
from decimal import Decimal

from django.test import TestCase

from apps.transformaciones.services import ia, limpieza, validacion


class LimpiezaTest(TestCase):
    def test_numeros_formato_chileno(self):
        casos = {
            "1.240,50": 1240.5, "18.400.000": 18400000, "42.900": 42900,
            "9.500": 9500, "9,5": 9.5, "1,00": 1.0, "96,80": 96.8,
        }
        for entrada, esperado in casos.items():
            self.assertAlmostEqual(limpieza._a_numero(entrada), esperado, places=2,
                msg=f"'{entrada}' se convirtió mal")

    def test_normaliza_unidades(self):
        cat = [{"simbolo": "m²", "alias": ["m2", "mt2"]},
               {"simbolo": "m³", "alias": ["m3", "mt3"]}]
        self.assertEqual(limpieza.normalizar_unidad("M2", cat), "m²")
        self.assertEqual(limpieza.normalizar_unidad("mt3", cat), "m³")
        self.assertIsNone(limpieza.normalizar_unidad("xyz", cat))


class IATest(TestCase):
    def test_anonimizacion_oculta_montos(self):
        import pandas as pd
        df = pd.DataFrame({"Precio": ["1000000"], "Desc": ["texto"]})
        muestra = ia._muestra_segura(df, ["Precio"], anonimizar=True)
        self.assertIn("<número oculto>", muestra["Precio"])
        self.assertNotIn("1000000", str(muestra["Precio"]))

    def test_modo_simulado_sin_clave(self):
        import pandas as pd
        df = pd.DataFrame({"Monto estimado": ["1000"]})
        campos = [{"nombre": "Presupuesto_CLP", "tipo": "MONEDA", "descripcion": "monto estimado"}]
        propuesta, modelo = ia.proponer_mapeo(df, ["Monto estimado"], campos, anonimizar=True)
        self.assertEqual(modelo, "heuristica-local")
        self.assertEqual(len(propuesta), 1)


class ValidacionTest(TestCase):
    class _P:
        def __init__(s, codigo, cap, es_cap, cant, precio, total, unidad=1):
            s.codigo=codigo; s.capitulo=cap; s.es_capitulo=es_cap
            s.cantidad=cant; s.precio_unitario=precio; s.total=total
            s.descripcion=codigo; s.unidad_canonica_id=unidad
        @property
        def total_calculado(s):
            if s.cantidad is None or s.precio_unitario is None: return None
            return Decimal(str(s.cantidad)) * Decimal(str(s.precio_unitario))

    def test_valida_cuando_todo_cuadra(self):
        P = self._P
        partidas = [
            P("1", "1", True, None, None, Decimal("30000")),
            P("1.1", "1", False, Decimal("2"), Decimal("10000"), Decimal("20000")),
            P("1.2", "1", False, Decimal("1"), Decimal("10000"), Decimal("10000")),
        ]
        r = validacion.validar(partidas, total_documento=Decimal("30000"))
        self.assertTrue(r["todo_ok"])

    def test_bloquea_cuando_linea_no_cuadra(self):
        P = self._P
        partidas = [P("1.1", "1", False, Decimal("2"), Decimal("10000"), Decimal("25000"))]
        r = validacion.validar(partidas)
        self.assertFalse(r["todo_ok"])

    def test_bloquea_sin_unidad(self):
        P = self._P
        partidas = [P("1.1", "1", False, Decimal("1"), Decimal("100"), Decimal("100"), unidad=None)]
        r = validacion.validar(partidas)
        self.assertFalse(r["todo_ok"])


class RevisionPlantillaTest(TestCase):
    """
    Caso real: 3 hojas de formulario con sus campos y una cuarta hoja que es una
    tabla, a la que se le agregó un campo inventado. Antes pasaba sin aviso.
    """

    def setUp(self):
        import os
        import tempfile
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Identificación"
        ws["A1"], ws["A2"] = "RUT del oferente", "Nombre del oferente"
        tabla = wb.create_sheet("Oferta")
        tabla.append(["Ítem", "Descripción", "Unidad", "Cantidad", "Precio unitario", "Total"])
        fd, self.ruta = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        wb.save(self.ruta)

    def tearDown(self):
        import os
        os.remove(self.ruta)

    def _campo(self, id, nombre, hoja, etiqueta=""):
        from types import SimpleNamespace
        return SimpleNamespace(id=id, nombre=nombre, hoja_destino=hoja,
                               etiqueta_busqueda=etiqueta, celda_destino="")

    def test_detecta_hoja_tabla_y_campos_que_no_se_podran_llenar(self):
        from apps.transformaciones.services import generacion
        campos = [
            self._campo(1, "RUT", "Identificación", "RUT del oferente"),
            self._campo(2, "Inventado", "Oferta", "Campo que no existe"),
            self._campo(3, "Total", "Oferta"),  # cae en el encabezado de la tabla
            self._campo(4, "Monto garantía extra", "Identificación"),  # 1 palabra en común no basta
        ]
        r = generacion.revisar_plantilla(self.ruta, campos)
        tipos = {h["nombre"]: h["tipo"] for h in r["hojas"]}
        self.assertEqual(tipos, {"Identificación": "formulario", "Oferta": "tabla"})
        self.assertNotIn("1", r["problemas"])
        self.assertEqual(r["ubicaciones"]["1"],
                         {"hoja": "Identificación", "celda": "B1",
                          "etiqueta": "RUT del oferente", "exacta": True})
        self.assertIn("no se encontró", r["problemas"]["2"])
        self.assertIn("dentro de la tabla", r["problemas"]["3"])
        self.assertIn("no se encontró", r["problemas"]["4"])

    def test_avisa_campos_sin_dato(self):
        from apps.transformaciones.services import generacion
        campos = [
            self._campo(1, "RUT", "Identificación", "RUT del oferente"),
            self._campo(2, "Nombre", "Identificación", "Nombre del oferente"),
        ]
        avisos = generacion.campos_sin_escribir(self.ruta, campos, {1: "12.345.678-5"})
        self.assertEqual(len(avisos), 1)
        self.assertIn("«Nombre» quedará vacío", avisos[0])
