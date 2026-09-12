"""
Pruebas del flujo de autenticación.

Corre con: python manage.py test apps.usuarios
Cubren el flujo completo de invitación y los permisos por rol.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.organizaciones.models import Organizacion
from apps.usuarios.models import Rol, Usuario


class FlujoAuthTest(TestCase):
    def setUp(self):
        self.org = Organizacion.objects.create(nombre="Test SpA", rut="761234567")
        self.gerente = Usuario.objects.create_user(
            email="gerente@test.cl", password="ClaveGerente1!",
            nombre_completo="Gerente Test", rol=Rol.GERENTE, organizacion=self.org)
        self.c = APIClient()

    def _login(self, email, password):
        r = self.c.post("/api/auth/login/", {"email": email, "password": password}, format="json")
        return r

    def test_login_gerente(self):
        r = self._login("gerente@test.cl", "ClaveGerente1!")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)
        self.assertEqual(r.data["usuario"]["rol"], "GERENTE")

    def test_flujo_invitacion_completo(self):
        # Gerente invita
        login = self._login("gerente@test.cl", "ClaveGerente1!")
        self.c.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        inv = self.c.post("/api/auth/invitar/",
            {"email": "trab@test.cl", "nombre_completo": "Trabajador"}, format="json")
        self.assertEqual(inv.status_code, 201)
        self.assertTrue(inv.data["usuario"]["necesita_crear_contrasena"])
        token = inv.data["token_invitacion"]

        # Trabajador crea contraseña
        self.c.credentials()
        cc = self.c.post("/api/auth/crear-contrasena/",
            {"token": token, "password": "ClaveTrab1!", "password2": "ClaveTrab1!"}, format="json")
        self.assertEqual(cc.status_code, 200)
        self.assertIn("access", cc.data)

        # Token no se puede reutilizar
        cc2 = self.c.post("/api/auth/crear-contrasena/",
            {"token": token, "password": "Otra12345!", "password2": "Otra12345!"}, format="json")
        self.assertEqual(cc2.status_code, 400)

    def test_trabajador_no_puede_invitar(self):
        login = self._login("gerente@test.cl", "ClaveGerente1!")
        self.c.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        inv = self.c.post("/api/auth/invitar/",
            {"email": "trab@test.cl", "nombre_completo": "Trabajador"}, format="json")
        token = inv.data["token_invitacion"]
        self.c.credentials()
        self.c.post("/api/auth/crear-contrasena/",
            {"token": token, "password": "ClaveTrab1!", "password2": "ClaveTrab1!"}, format="json")

        # Trabajador logueado intenta invitar → 403
        tl = self._login("trab@test.cl", "ClaveTrab1!")
        self.c.credentials(HTTP_AUTHORIZATION=f"Bearer {tl.data['access']}")
        r = self.c.post("/api/auth/invitar/",
            {"email": "otro@test.cl", "nombre_completo": "Otro"}, format="json")
        self.assertEqual(r.status_code, 403)
