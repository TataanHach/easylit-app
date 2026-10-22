"""
Limpieza con pandas (services/normalizacion.py): lo que antes se le pedía a la
IA y ahora resuelven reglas fijas.

Corre con: python manage.py test apps.transformaciones.tests_normalizacion
"""
from datetime import date, datetime

import pandas as pd
from django.test import SimpleTestCase

from apps.transformaciones.services import normalizacion as n


class FechasTest(SimpleTestCase):
    def test_formatos_chilenos(self):
        casos = {
            "15/08/2024": "15-08-2024",
            "15-08-24": "15-08-2024",
            "2024-08-15": "15-08-2024",
            "2024-08-15 00:00:00": "15-08-2024",
            "15 de agosto de 2024": "15-08-2024",
            "15-ago-2024": "15-08-2024",
            "Jueves 15 de Agosto, 2024 a las 15:00 hrs": "15-08-2024",
            "Agosto 2024 aprox.": "08-2024",
            "septiembre de 2025": "09-2025",
        }
        serie = pd.Series(list(casos), dtype="object")
        self.assertEqual(list(n.fechas(serie)), list(casos.values()))

    def test_no_inventa_fechas(self):
        serie = pd.Series(["31/02/2024", "hola", "Plaza de Armas"], dtype="object")
        self.assertTrue(n.fechas(serie).isna().all())

    def test_fecha_de_excel_lee_el_dia_primero(self):
        df = pd.DataFrame([{"Fecha cierre": datetime(2024, 9, 1)}])
        self.assertEqual(n.limpiar_dataframe(df)[0].iloc[0, 0], "01-09-2024")
        self.assertEqual(n.fecha("01/09/2024"), date(2024, 9, 1))


class ReglasTest(SimpleTestCase):
    def test_rut_solo_si_el_digito_es_valido(self):
        self.assertEqual(n.rut("12345678-5"), "12.345.678-5")
        self.assertEqual(n.rut("12.345.678-9"), None)

    def test_numeros_en_palabras_y_plazos(self):
        self.assertEqual(n.numero_en_palabras("ciento veinte días corridos"), 120)
        self.assertEqual(n.numero_en_palabras("dos mil quinientos"), 2500)
        self.assertIsNone(n.numero_en_palabras("contra factura"))
        serie = pd.Series(["sesenta ( 60 ) Días", "120 dias de corrido", "noventa días", "a convenir"])
        resultado = n.plazos(serie)
        self.assertEqual(list(resultado[:3]), ["60", "120", "90"])
        self.assertTrue(pd.isna(resultado[3]))   # no es un número: no se toca

    def test_nombres_de_personas(self):
        self.assertEqual(n.nombre_persona("JUAN PEREZ DE LA FUENTE"), "Juan Perez de la Fuente")
        self.assertEqual(n.nombre_persona("McDonald Soto"), "McDonald Soto")  # mezclado: se respeta

    def test_tildes_sin_ambiguedad(self):
        serie = pd.Series(["Pavimentacion region del Biobio", "CONSTRUCCION", "contacto@empresa.cl"])
        self.assertEqual(list(n.tildes(serie)),
                         ["Pavimentación región del Biobío", "CONSTRUCCIÓN", "contacto@empresa.cl"])

    def test_unidades(self):
        serie = pd.Series(["1200 mts2", "15 metros cubicos", "Lote ml"])
        self.assertEqual(list(n.unidades(serie)), ["1200 m2", "15 m3", "Lote ml"])


class DataFrameTest(SimpleTestCase):
    def test_limpia_cada_columna_segun_su_tipo(self):
        df = pd.DataFrame([{
            "Fecha de apertura": "15 de agosto de 2024",
            "Rut representante": "12345678-5",
            "Código": "12-10-25",                      # parece fecha, pero no es: se respeta
            "Correo": "Juan.Perez @Empresa.CL",
            "Plazo de ejecución": "sesenta ( 60 ) Días",
            "Representante legal": "juan pablo perez (RUT 15234987-k)",
            "Nombre de la empresa": "CONSTRUCTORA ABC SPA",  # empresa: no se cambia a "Abc"
            "Descripción": "Construccion  de camarines",
            "Total": "#VALUE!",
            "Monto": 1500000,
        }])
        limpio, resumen = n.limpiar_dataframe(df)
        self.assertEqual(limpio.iloc[0].to_dict(), {
            "Fecha de apertura": "15-08-2024",
            "Rut representante": "12.345.678-5",
            "Código": "12-10-25",
            "Correo": "juan.perez@empresa.cl",
            "Plazo de ejecución": "60",
            "Representante legal": "Juan Pablo Perez",
            "Nombre de la empresa": "CONSTRUCTORA ABC SPA",
            "Descripción": "Construcción de camarines",
            "Total": None,                             # error de fórmula: vacío
            "Monto": 1500000,
        })
        self.assertEqual(resumen["errores_excel"], 1)

    def test_lo_resuelto_por_reglas_no_va_a_la_ia(self):
        for valor in ("15-08-2024", "12.345.678-5", "a@b.cl", "$ 150.000.000.- (ciento cincuenta millones)", "1200 m2"):
            self.assertTrue(n.resuelto_por_reglas(valor), valor)
        self.assertFalse(n.resuelto_por_reglas("Constructora y Servi cios Spa"))

