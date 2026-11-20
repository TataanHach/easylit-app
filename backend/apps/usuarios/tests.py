"""
Pruebas del flujo de autenticación.

Corre con: python manage.py test apps.usuarios
Cubren el flujo completo de invitación y los permisos por rol.
"""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.organizaciones.models import Organizacion
from apps.usuarios.models import Rol, Usuario


class FlujoAuthTest(TestCase):
    def setUp(self):
        cache.clear()   # los límites de intentos guardan sus contadores en la caché
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
            {"email": "trab@test.cl", "nombre_completo": "Trabajador", "rut": "11.111.111-1"}, format="json")
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
            {"email": "trab@test.cl", "nombre_completo": "Trabajador", "rut": "11.111.111-1"}, format="json")
        token = inv.data["token_invitacion"]
        self.c.credentials()
        self.c.post("/api/auth/crear-contrasena/",
            {"token": token, "password": "ClaveTrab1!", "password2": "ClaveTrab1!"}, format="json")

        # Trabajador logueado intenta invitar → 403
        tl = self._login("trab@test.cl", "ClaveTrab1!")
        self.c.credentials(HTTP_AUTHORIZATION=f"Bearer {tl.data['access']}")
        r = self.c.post("/api/auth/invitar/",
            {"email": "otro@test.cl", "nombre_completo": "Otro", "rut": "22.222.222-2"}, format="json")
        self.assertEqual(r.status_code, 403)


class ValidacionesAuthTest(TestCase):
    """Validaciones mínimas: espacios, mayúsculas, largos, RUT y cierre de sesión."""

    def setUp(self):
        cache.clear()   # los límites de intentos guardan sus contadores en la caché
        self.org = Organizacion.objects.create(nombre="Test SpA", rut="761234567")
        Usuario.objects.create_user(
            email="gerente@test.cl", password="ClaveGerente1!",
            nombre_completo="Gerente Test", rol=Rol.GERENTE, organizacion=self.org)
        self.c = APIClient()

    def _login(self, email, password="ClaveGerente1!"):
        return self.c.post("/api/auth/login/", {"email": email, "password": password}, format="json")

    def test_login_ignora_espacios_y_mayusculas_del_correo(self):
        self.assertEqual(self._login("  Gerente@Test.CL  ").status_code, 200)

    def test_login_fallido_da_mensaje_claro(self):
        r = self._login("gerente@test.cl", "Incorrecta1!")
        self.assertEqual(r.status_code, 401)
        self.assertIn("Correo o contraseña incorrectos", r.data["detail"])

    def test_correo_demasiado_largo_se_rechaza(self):
        r = self.c.post("/api/auth/estado-correo/", {"email": "a" * 250 + "@x.cl"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_logout_invalida_el_refresh(self):
        refresh = self._login("gerente@test.cl").data["refresh"]
        self.assertEqual(self.c.post("/api/auth/logout/", {"refresh": refresh}, format="json").status_code, 204)
        r = self.c.post("/api/auth/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_rut_con_digito_incorrecto_se_rechaza(self):
        login = self._login("gerente@test.cl")
        self.c.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        malo = self.c.post("/api/auth/invitar/",
            {"email": "t1@test.cl", "nombre_completo": "T", "rut": "12.345.678-9"}, format="json")
        self.assertEqual(malo.status_code, 400)
        self.assertIn("rut", malo.data)
        bueno = self.c.post("/api/auth/invitar/",
            {"email": "t2@test.cl", "nombre_completo": "T", "rut": "12.345.678-5"}, format="json")
        self.assertEqual(bueno.status_code, 201)
        self.assertEqual(bueno.data["usuario"]["rut"], "123456785")


class EquipoTest(TestCase):
    """Pantalla Equipo: el gerente ve y da acceso solo a la gente de su organización."""

    def setUp(self):
        cache.clear()   # los límites de intentos guardan sus contadores en la caché
        self.org = Organizacion.objects.create(nombre="Test SpA", rut="761234567")
        self.otra = Organizacion.objects.create(nombre="Otra SpA", rut="765432103")
        Usuario.objects.create_user(
            email="gerente@test.cl", password="ClaveGerente1!",
            nombre_completo="Gerente Test", rol=Rol.GERENTE, organizacion=self.org)
        Usuario.objects.create_user(
            email="ajeno@otra.cl", password="ClaveAjeno1!",
            nombre_completo="Ajeno", rol=Rol.TRABAJADOR, organizacion=self.otra)
        self.c = APIClient()
        login = self.c.post("/api/auth/login/",
            {"email": "gerente@test.cl", "password": "ClaveGerente1!"}, format="json")
        self.c.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    def _invitar(self, email="trab@test.cl", rut="11.111.111-1"):
        return self.c.post("/api/auth/invitar/",
            {"email": email, "nombre_completo": "Trabajador", "rut": rut}, format="json")

    def _estados(self):
        r = self.c.get("/api/auth/equipo/")
        self.assertEqual(r.status_code, 200)
        return {m["email"]: m for m in r.data}

    def test_invitar_sin_rut_se_rechaza(self):
        r = self.c.post("/api/auth/invitar/",
            {"email": "trab@test.cl", "nombre_completo": "Trabajador"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("rut", r.data)
        self.assertFalse(Usuario.objects.filter(email="trab@test.cl").exists())

    def test_rut_repetido_se_rechaza(self):
        self.assertEqual(self._invitar().status_code, 201)
        r = self._invitar(email="otro@test.cl", rut="11111111-1")
        self.assertEqual(r.status_code, 400)
        self.assertIn("rut", r.data)

    def test_lista_solo_mi_organizacion_con_estados(self):
        codigo = self._invitar().data["token_invitacion"]
        # Creado "desde el admin": sin invitación ni contraseña.
        Usuario.objects.create_user(email="admin@test.cl", nombre_completo="Desde Admin",
                                    rol=Rol.TRABAJADOR, organizacion=self.org)
        equipo = self._estados()
        self.assertNotIn("ajeno@otra.cl", equipo)
        self.assertEqual(equipo["gerente@test.cl"]["estado"], "ACTIVO")
        self.assertEqual(equipo["trab@test.cl"]["estado"], "PENDIENTE")
        self.assertEqual(equipo["admin@test.cl"]["estado"], "SIN_INVITACION")
        # El código se ve una sola vez: la lista nunca lo devuelve.
        self.assertNotIn("codigo", equipo["trab@test.cl"])
        self.assertNotIn(codigo, str(equipo))

    def test_codigo_8_caracteres_y_no_queda_legible_en_la_base(self):
        from apps.usuarios.models import ALFABETO_CODIGO, Invitacion
        codigo = self._invitar().data["token_invitacion"]
        self.assertRegex(codigo, r"^[A-Z0-9]{4}-[A-Z0-9]{4}$")
        self.assertTrue(all(c in ALFABETO_CODIGO for c in codigo.replace("-", "")))
        guardado = Invitacion.objects.get(usuario__email="trab@test.cl").codigo_hash
        self.assertEqual(len(guardado), 64)
        self.assertNotIn(codigo.replace("-", ""), guardado)

    def test_codigo_sirve_en_minusculas_sin_guion_y_con_espacios(self):
        codigo = self._invitar().data["token_invitacion"]
        self.c.credentials()
        escrito = " " + codigo.replace("-", "").lower() + " "
        r = self.c.post("/api/auth/crear-contrasena/",
            {"token": escrito, "password": "ClaveTrab1!", "password2": "ClaveTrab1!"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_codigo_con_formato_malo_se_explica(self):
        self.c.credentials()
        r = self.c.post("/api/auth/crear-contrasena/",
            {"token": "ABC", "password": "ClaveTrab1!", "password2": "ClaveTrab1!"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("8 letras y números", str(r.data["token"]))

    def test_nuevo_codigo_anula_el_anterior(self):
        viejo = self._invitar().data["token_invitacion"]
        uid = Usuario.objects.get(email="trab@test.cl").id
        r = self.c.post(f"/api/auth/equipo/{uid}/invitacion/")
        self.assertEqual(r.status_code, 201)
        nuevo = r.data["token_invitacion"]
        self.assertNotEqual(viejo, nuevo)

        self.c.credentials()
        datos = {"password": "ClaveTrab1!", "password2": "ClaveTrab1!"}
        self.assertEqual(self.c.post("/api/auth/crear-contrasena/",
            {"token": viejo, **datos}, format="json").status_code, 400)
        self.assertEqual(self.c.post("/api/auth/crear-contrasena/",
            {"token": nuevo, **datos}, format="json").status_code, 200)

    def test_codigo_para_creado_desde_admin(self):
        u = Usuario.objects.create_user(email="admin@test.cl", nombre_completo="Desde Admin",
                                        rol=Rol.TRABAJADOR, organizacion=self.org)
        r = self.c.post(f"/api/auth/equipo/{u.id}/invitacion/")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self._estados()["admin@test.cl"]["estado"], "PENDIENTE")

    def test_no_da_codigo_a_otra_organizacion_ni_a_quien_ya_entra(self):
        ajeno = Usuario.objects.get(email="ajeno@otra.cl")
        self.assertEqual(self.c.post(f"/api/auth/equipo/{ajeno.id}/invitacion/").status_code, 404)
        yo = Usuario.objects.get(email="gerente@test.cl")
        self.assertEqual(self.c.post(f"/api/auth/equipo/{yo.id}/invitacion/").status_code, 400)

    def test_trabajador_no_ve_el_equipo(self):
        self.c.credentials()
        login = self.c.post("/api/auth/login/",
            {"email": "ajeno@otra.cl", "password": "ClaveAjeno1!"}, format="json")
        self.c.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        self.assertEqual(self.c.get("/api/auth/equipo/").status_code, 403)


class LimiteDeIntentosTest(TestCase):
    """Los endpoints públicos frenan a quien prueba muchas veces seguidas."""

    def setUp(self):
        cache.clear()
        self.c = APIClient()
        self.org = Organizacion.objects.create(nombre="Lim SpA", rut="761111111")
        Usuario.objects.create_user(email="lim@test.cl", password="ClaveLim1!",
                                    nombre_completo="Lim", rol=Rol.GERENTE, organizacion=self.org)

    def _hasta_bloqueo(self, url, datos, maximo):
        for _ in range(maximo):
            r = self.c.post(url, datos, format="json")
            self.assertNotEqual(r.status_code, 429)
        return self.c.post(url, datos, format="json")

    def test_crear_contrasena_bloquea_tras_20_intentos(self):
        datos = {"token": "AAAA-BBBB", "password": "ClaveTrab1!", "password2": "ClaveTrab1!"}
        r = self._hasta_bloqueo("/api/auth/crear-contrasena/", datos, 20)
        self.assertEqual(r.status_code, 429)
        self.assertIn("demasiados intentos", r.data["detail"])
        self.assertIn("Retry-After", r.headers)

    def test_login_bloquea_por_ip(self):
        datos = {"email": "lim@test.cl", "password": "Mala1234!"}
        r = self._hasta_bloqueo("/api/auth/login/", datos, 10)
        self.assertEqual(r.status_code, 429)

    def test_login_bloquea_por_cuenta_aunque_cambie_la_ip(self):
        datos = {"email": "lim@test.cl", "password": "Mala1234!"}
        for i in range(20):
            r = self.c.post("/api/auth/login/", datos, format="json", REMOTE_ADDR=f"10.0.0.{i + 1}")
            self.assertNotEqual(r.status_code, 429)
        r = self.c.post("/api/auth/login/", datos, format="json", REMOTE_ADDR="10.0.1.1")
        self.assertEqual(r.status_code, 429)

    def test_estado_correo_bloquea_tras_30(self):
        r = self._hasta_bloqueo("/api/auth/estado-correo/", {"email": "x@test.cl"}, 30)
        self.assertEqual(r.status_code, 429)
