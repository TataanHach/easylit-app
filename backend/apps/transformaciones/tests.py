"""
Pruebas de transformaciones: alcance (Mías/Equipo/Todas) y aislamiento entre
organizaciones. Lo segundo es crítico: una empresa jamás debe ver datos de otra.

Corre con: python manage.py test apps.transformaciones
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.organizaciones.models import Organizacion
from apps.plantillas.models import Plantilla
from apps.transformaciones.models import Transformacion
from apps.usuarios.models import Rol, Usuario


class AlcanceYAislamientoTest(TestCase):
    def setUp(self):
        # Dos organizaciones distintas
        self.org_a = Organizacion.objects.create(nombre="Constructora A", rut="111111111")
        self.org_b = Organizacion.objects.create(nombre="Constructora B", rut="222222222")

        # Usuarios de la org A: un gerente y un trabajador
        self.gerente_a = Usuario.objects.create_user(
            email="ger_a@a.cl", password="Clave1234!", nombre_completo="Gerente A",
            rol=Rol.GERENTE, organizacion=self.org_a)
        self.trab_a = Usuario.objects.create_user(
            email="trab_a@a.cl", password="Clave1234!", nombre_completo="Trabajador A",
            rol=Rol.TRABAJADOR, organizacion=self.org_a)
        # Usuario de la org B
        self.ger_b = Usuario.objects.create_user(
            email="ger_b@b.cl", password="Clave1234!", nombre_completo="Gerente B",
            rol=Rol.GERENTE, organizacion=self.org_b)

        # Una plantilla por organización
        self.plant_a = Plantilla.objects.create(
            organizacion=self.org_a, nombre="Formato A",
            archivo=SimpleUploadedFile("a.xlsx", b"x"))
        self.plant_b = Plantilla.objects.create(
            organizacion=self.org_b, nombre="Formato B",
            archivo=SimpleUploadedFile("b.xlsx", b"x"))

        # Transformaciones: 2 del gerente A, 1 del trabajador A, 1 de la org B
        for i in range(2):
            Transformacion.objects.create(
                organizacion=self.org_a, autor=self.gerente_a, plantilla=self.plant_a,
                archivo_origen=SimpleUploadedFile(f"g{i}.xlsx", b"x"), nombre_origen=f"ger_a_{i}.xlsx")
        Transformacion.objects.create(
            organizacion=self.org_a, autor=self.trab_a, plantilla=self.plant_a,
            archivo_origen=SimpleUploadedFile("t.xlsx", b"x"), nombre_origen="trab_a.xlsx")
        Transformacion.objects.create(
            organizacion=self.org_b, autor=self.ger_b, plantilla=self.plant_b,
            archivo_origen=SimpleUploadedFile("b.xlsx", b"x"), nombre_origen="org_b.xlsx")

        self.c = APIClient()

    def _login(self, email):
        r = self.c.post("/api/auth/login/", {"email": email, "password": "Clave1234!"}, format="json")
        self.c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_alcance_mias(self):
        self._login("ger_a@a.cl")
        r = self.c.get("/api/transformaciones/?alcance=mine")
        self.assertEqual(r.status_code, 200)
        # El gerente A tiene 2 propias
        self.assertEqual(len(r.data), 2)

    def test_alcance_equipo(self):
        self._login("ger_a@a.cl")
        r = self.c.get("/api/transformaciones/?alcance=team")
        # Del equipo (no suyas) hay 1: la del trabajador A
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["autor_nombre"], "Trabajador A")

    def test_alcance_todas(self):
        self._login("ger_a@a.cl")
        r = self.c.get("/api/transformaciones/?alcance=all")
        # Todas las de la org A: 3 (nunca la de org B)
        self.assertEqual(len(r.data), 3)

    def test_aislamiento_entre_organizaciones(self):
        # CRÍTICO: el gerente A no debe ver NADA de la org B, con ningún alcance.
        self._login("ger_a@a.cl")
        for alcance in ("mine", "team", "all"):
            r = self.c.get(f"/api/transformaciones/?alcance={alcance}")
            nombres = [t["nombre_origen"] for t in r.data]
            self.assertNotIn("org_b.xlsx", nombres,
                f"FUGA DE DATOS: la org A vio datos de la org B con alcance={alcance}")

    def test_plantillas_aisladas(self):
        # El gerente A solo ve su plantilla, no la de la org B.
        self._login("ger_a@a.cl")
        r = self.c.get("/api/plantillas/")
        nombres = [p["nombre"] for p in r.data]
        self.assertIn("Formato A", nombres)
        self.assertNotIn("Formato B", nombres)

    def test_no_se_puede_usar_plantilla_de_otra_org(self):
        # El gerente A intenta crear una transformación con la plantilla de B.
        self._login("ger_a@a.cl")
        r = self.c.post("/api/transformaciones/", {
            "archivo_origen": SimpleUploadedFile("x.xlsx", b"x"),
            "nombre_origen": "intento.xlsx",
            "plantilla": str(self.plant_b.id),
        }, format="multipart")
        self.assertEqual(r.status_code, 400)  # rechazado por validación
