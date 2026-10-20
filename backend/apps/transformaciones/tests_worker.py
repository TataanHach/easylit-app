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


class CompletarMapeoTest(TestCase):
    def test_campo_obvio_que_la_ia_dejo_sin_dato_se_completa(self):
        muestra = {"RUT": ["76.453.212-0"], "Representante Legal": ["Juan"], "Glosa": ["x"]}
        campos = [{"nombre": "RUT Legal", "tipo": "TEXTO"}, {"nombre": "Representante", "tipo": "TEXTO"},
                  {"nombre": "Observaciones", "tipo": "TEXTO"}]
        propuesta = [
            {"origen": "RUT", "destino": None, "confianza": 0, "motivo": ""},
            {"origen": "Representante Legal", "destino": "Representante", "confianza": 100, "motivo": ""},
        ]
        resultado = ia._completar_por_nombre(propuesta, muestra, campos)
        por_origen = {p["origen"]: p["destino"] for p in resultado}
        self.assertEqual(por_origen["RUT"], "RUT Legal")
        self.assertEqual(por_origen["Representante Legal"], "Representante")   # lo de la IA se respeta
        self.assertNotIn("Glosa", por_origen)   # sin coincidencia fuerte: no se inventa


class GenerarConValoresTest(TestCase):
    """Genera un documento con campos con valor (el error de `ws` no tenía test)."""

    def test_escribe_los_campos_junto_a_su_etiqueta(self):
        import io
        import os
        import tempfile
        from types import SimpleNamespace
        from openpyxl import Workbook, load_workbook
        from apps.transformaciones.services import generacion

        wb = Workbook()
        wb.active.title = "Identificación"
        wb.active["A1"], wb.active["A2"] = "RUT:", "Fecha de apertura:"
        fd, ruta = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        wb.save(ruta)
        self.addCleanup(os.remove, ruta)

        def campo(nombre, etiqueta, tipo="TEXTO"):
            return SimpleNamespace(id=nombre, nombre=nombre, etiqueta_busqueda=etiqueta, hoja_destino="",
                                   celda_destino="", tipo=tipo, formato_numero="NINGUNO")
        contenido = generacion.generar_documento(ruta, [
            {"campo": campo("RUT Legal", "RUT"), "valor": "12345678-5"},
            {"campo": campo("Apertura", "Fecha de apertura", "FECHA"), "valor": "15-08-2024"},
        ])
        ws = load_workbook(io.BytesIO(contenido)).active
        self.assertEqual(ws["B1"].value, "12.345.678-5")
        self.assertEqual(ws["B2"].value.date().isoformat(), "2024-08-15")   # fecha real de Excel


class GenerarTablasTest(TestCase):
    """Caso real: evaluación económica con fórmulas, tablas lado a lado y celdas combinadas."""

    def _guardar(self, wb):
        import os
        import tempfile
        fd, ruta = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        wb.save(ruta)
        self.addCleanup(os.remove, ruta)
        return ruta

    def test_montos_con_decimales_no_se_multiplican(self):
        from apps.transformaciones.services import generacion
        self.assertEqual(generacion._limpiar_monto("5970672.7636"), "5970672.7636")
        self.assertEqual(generacion._limpiar_monto("1.500.000"), "1500000")
        self.assertEqual(generacion._limpiar_numero("2.5"), "2.5")
        self.assertEqual(generacion._limpiar_numero("1.500"), "1500")
        self.assertEqual(generacion._limpiar_numero("0.125"), "0.125")

    def test_vista_previa_muestra_montos_en_formato_chileno(self):
        from types import SimpleNamespace
        from apps.transformaciones.services import generacion
        campo = SimpleNamespace(nombre="RRHH", etiqueta_busqueda="", formato_numero="PESOS", tipo="NUMERO")
        self.assertEqual(generacion.texto_campo("5970672.7636", campo), "$5.970.673")

    def test_tablas_lado_a_lado_combinadas_y_formulas(self):
        import io
        from openpyxl import Workbook, load_workbook
        from apps.transformaciones.services import generacion

        encabezado = [None, "ITEM", "PRODUCTO", "CANTIDAD", "SUB TOTAL", None, "ITEM", "PRODUCTO", "HORAS", "SUB TOTAL"]
        origen = Workbook()
        o = origen.active
        o.title = "EQUIPOS"
        o.append(encabezado)
        o.append([None, 1, "COMPUTADOR", 3, 1740000, None, 1, "COMPUTADOR", 981, 87805.5])
        o.append([None, 0, 0, 0, 0])                 # fila de fórmulas en 0: no es dato
        o.append([None, 2, "CELULAR", 1, 270000, None, 2, "CELULAR", 695, 28958.3])
        o.append([])
        o.append([])
        o.append([None, "FACTORES:", 0.25])          # otro bloque bajo la tabla: no es partida
        o2 = origen.create_sheet("OTRA")
        o2.append(["Descripción", "Cantidad", "Total"])
        o2.append(["Algo", 1, 10])

        plantilla = Workbook()
        p = plantilla.active
        p.title = "EQUIPOS"
        p.append(encabezado)
        p["E3"] = "=D3*2"                            # fórmula de la plantilla: se respeta
        p.merge_cells("B7:C7")                       # celda combinada donde no se escribe
        p2 = plantilla.create_sheet("OTRA")
        p2.append(["Descripción", "Cantidad", "Total"])

        contenido = generacion.generar_documento(
            self._guardar(plantilla), [], ruta_origen=self._guardar(origen))
        wb = load_workbook(io.BytesIO(contenido))
        ws = wb["EQUIPOS"]
        self.assertEqual(ws["E2"].value, 1740000)    # la tabla izquierda no toma el SUB TOTAL derecho
        self.assertEqual(ws["J2"].value, 87805.5)
        self.assertEqual(ws["E3"].value, "=D3*2")
        self.assertEqual(ws["C4"].value, "CELULAR")  # misma fila que en el origen
        self.assertIsNone(ws["B7"].value)            # el bloque de factores no se copia
        self.assertEqual(wb["OTRA"]["A2"].value, "Algo")   # las hojas siguientes se llenan
        self.assertTrue(wb.calculation.fullCalcOnLoad)


class ColumnasConIATest(TestCase):
    """Columnas de tabla que no calzan por nombre: la IA sugiere, el código valida."""

    def test_solo_se_aceptan_columnas_preguntadas_existentes_y_con_confianza(self):
        import json
        from unittest import mock
        from django.test import override_settings
        pedido = {"Hoja": {"sin_pareja": ["Fono", "Numero"],
                           "origen": {"Telefono": ["+56 9 1111 2222"], "Nombre": ["Ana"]}}}
        respuesta = json.dumps([
            {"hoja": "Hoja", "destino": "Fono", "origen": "Telefono", "confianza": 95, "motivo": "sinónimo"},
            {"hoja": "Hoja", "destino": "Numero", "origen": "Inventada", "confianza": 90},   # no existe
            {"hoja": "Hoja", "destino": "Nombre", "origen": "Nombre", "confianza": 90},      # no se preguntó
            {"hoja": "Hoja", "destino": "Numero", "origen": "Nombre", "confianza": 30},      # confianza baja
        ])
        with override_settings(GEMINI_API_KEY="x"), \
                mock.patch.object(ia, "_llamar_gemini", return_value=respuesta):
            sugerencias, _ = ia.sugerir_columnas_tablas(pedido)
        self.assertEqual(list(sugerencias["Hoja"]), ["Fono"])
        self.assertEqual(sugerencias["Hoja"]["Fono"]["origen"], "Telefono")

    def test_sin_clave_no_se_llama_a_la_ia(self):
        from unittest import mock
        from django.test import override_settings
        with override_settings(GEMINI_API_KEY=""), mock.patch.object(ia, "_llamar_gemini") as llamada:
            self.assertEqual(ia.sugerir_columnas_tablas({"H": {"sin_pareja": ["a"], "origen": {}}})[0], {})
        llamada.assert_not_called()

    def test_la_pareja_por_nombre_manda_sobre_la_de_la_ia(self):
        from apps.transformaciones.services import generacion
        mapa = generacion._emparejar_columnas(
            ["Telefono", "Correo"], ["Fono", "Correo"], {"Fono": "Telefono", "Correo": "Telefono"})
        self.assertEqual(mapa, {"Fono": "Telefono", "Correo": "Correo"})

    def test_lo_que_elige_el_usuario_manda_sobre_nombre_e_ia(self):
        from apps.transformaciones.services import generacion
        parejas = generacion.parejas_columnas(
            ["Nombre", "Correo", "Telefono"], ["Numero", "Nombre", "Correo", "Fono"],
            sugeridas={"Fono": "Telefono", "Numero": "Correo"},
            usuario={"Numero": "Telefono", "Correo": ""})
        self.assertEqual(parejas, {
            "Numero": ("Telefono", "usuario"),   # elegida: gana a la IA
            "Nombre": ("Nombre", "nombre"),
            "Correo": (None, "usuario"),         # el usuario la dejó vacía a propósito
            "Fono": ("Telefono", "ia"),
        })


class CopiarFormulasTest(TestCase):
    """Las fórmulas del origen se copian a la tabla solo cuando es seguro."""

    def _generar(self, origen, plantilla):
        import io
        import os
        import tempfile
        from openpyxl import load_workbook
        from apps.transformaciones.services import generacion
        rutas = []
        for wb in (origen, plantilla):
            fd, ruta = tempfile.mkstemp(suffix=".xlsx")
            os.close(fd)
            wb.save(ruta)
            self.addCleanup(os.remove, ruta)
            rutas.append(ruta)
        return load_workbook(io.BytesIO(generacion.generar_documento(rutas[1], [], ruta_origen=rutas[0])))

    def _libros(self, fila_plantilla=1, con_nombre=True):
        from openpyxl import Workbook
        from openpyxl.workbook.defined_name import DefinedName
        origen, plantilla = Workbook(), Workbook()
        for wb in (origen, plantilla):
            wb.active.title = "Tabla"
            wb.create_sheet("Datos")["A1"] = 2
        o = origen.active
        o.append(["Descripción", "Cantidad", "Precio", "Total"])
        o.append(["Uno", 2, 100, "=B2*C2"])
        o.append(["Dos", 3, 50, "=B3*C3*factor"])
        o.append(["Tres", 1, 10, "=C4*Datos!A1"])
        for wb in (origen, plantilla) if con_nombre else (origen,):
            wb.defined_names["factor"] = DefinedName("factor", attr_text="Datos!$A$1")
        p = plantilla.active
        for _ in range(fila_plantilla - 1):
            p.append([])
        p.append(["Descripción", "Cantidad", "Precio", "Total"])
        return origen, plantilla

    def test_misma_forma_copia_las_formulas(self):
        ws = self._generar(*self._libros())["Tabla"]
        self.assertEqual([ws["D2"].value, ws["D3"].value, ws["D4"].value],
                         ["=B2*C2", "=B3*C3*factor", "=C4*Datos!A1"])

    def test_tabla_corrida_ajusta_y_no_copia_referencias_a_otras_hojas(self):
        ws = self._generar(*self._libros(fila_plantilla=3))["Tabla"]
        self.assertEqual(ws["D4"].value, "=B4*C4")         # ajustada 2 filas, como al pegar en Excel
        self.assertEqual(ws["D5"].value, "=B5*C5*factor")
        self.assertIsNone(ws["D6"].value)                   # otra hoja + tabla corrida: no se adivina

    def test_sin_el_nombre_definido_en_la_plantilla_no_se_copia(self):
        ws = self._generar(*self._libros(con_nombre=False))["Tabla"]
        self.assertEqual(ws["D2"].value, "=B2*C2")
        self.assertNotIsInstance(ws["D3"].value, str)       # iría a #NAME?: queda el valor (o vacía)
