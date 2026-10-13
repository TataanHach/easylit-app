"""
Autenticación con Firebase.

Firebase guarda los correos y contraseñas y hace el inicio de sesión en el
navegador. Django sigue siendo dueño de roles, organización e invitaciones: en
cada petición verifica el token de Firebase y busca al Usuario vinculado a ese
uid. Nadie entra solo por tener una cuenta en Firebase; hay que haber sido
invitado (o vinculado por un administrador con `manage.py vincular_firebase`).

Se usan las APIs REST de Google por HTTPS (google-auth + requests), sin el SDK
firebase-admin: ese SDK depende de gRPC, cuyo .dll lo bloquea el Control de
aplicaciones de Windows.

Se activa definiendo FIREBASE_PROJECT_ID. Sin él, la app usa el login propio
(JWT), como en desarrollo.
"""
import json
import time

import requests
from django.conf import settings
from google.auth import jwt as google_jwt
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account
from rest_framework import authentication, exceptions

_URL_CERTIFICADOS = (
    "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
)
_URL_CUENTAS = "https://identitytoolkit.googleapis.com/v1/projects/{proyecto}/accounts"
_certificados = {"datos": None, "vence": 0.0}


def activo():
    return bool(getattr(settings, "FIREBASE_PROJECT_ID", ""))


def _certs():
    """Certificados públicos de Google para verificar tokens, en caché según Cache-Control."""
    if _certificados["datos"] and time.time() < _certificados["vence"]:
        return _certificados["datos"]
    resp = requests.get(_URL_CERTIFICADOS, timeout=10)
    resp.raise_for_status()
    edad = 3600
    for parte in resp.headers.get("Cache-Control", "").split(","):
        if parte.strip().startswith("max-age="):
            edad = int(parte.strip()[8:])
    _certificados.update(datos=resp.json(), vence=time.time() + edad)
    return _certificados["datos"]


def verificar_token(token):
    """Valida un ID token de Firebase y devuelve sus datos (uid en 'sub'). Lanza ValueError."""
    proyecto = settings.FIREBASE_PROJECT_ID
    datos = google_jwt.decode(token, certs=_certs(), audience=proyecto, clock_skew_in_seconds=10)
    if datos.get("iss") != f"https://securetoken.google.com/{proyecto}":
        raise ValueError("El token no es de este proyecto de Firebase.")
    if not datos.get("sub"):
        raise ValueError("El token no trae usuario.")
    return datos


def _sesion_admin():
    """Sesión autorizada con la cuenta de servicio (para crear o cambiar cuentas)."""
    info = getattr(settings, "FIREBASE_CREDENCIALES", "")
    if not info:
        raise RuntimeError(
            "Falta FIREBASE_CREDENCIALES (el JSON de la cuenta de servicio de Firebase) "
            "en la configuración del servidor."
        )
    credenciales = service_account.Credentials.from_service_account_info(
        json.loads(info), scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return AuthorizedSession(credenciales)


def crear_o_actualizar_cuenta(email, password, nombre=""):
    """
    Crea la cuenta de Firebase de un usuario invitado (o le cambia la contraseña
    si ya existía) y devuelve su uid. El correo queda verificado: la invitación
    llegó a ese correo, así que ya se comprobó que es suyo.
    """
    sesion = _sesion_admin()
    url = _URL_CUENTAS.format(proyecto=settings.FIREBASE_PROJECT_ID)
    resp = sesion.post(url, json={
        "email": email, "password": password, "displayName": nombre, "emailVerified": True,
    }, timeout=15)
    if resp.ok:
        return resp.json()["localId"]
    if "EMAIL_EXISTS" not in resp.text:
        raise RuntimeError(f"Firebase no pudo crear la cuenta: {resp.text[:300]}")

    # Ya existía (por ejemplo, un intento anterior): se le fija la contraseña nueva.
    busqueda = sesion.post(f"{url}:lookup", json={"email": [email]}, timeout=15)
    busqueda.raise_for_status()
    uid = busqueda.json()["users"][0]["localId"]
    cambio = sesion.post(f"{url}:update", json={
        "localId": uid, "password": password, "emailVerified": True,
    }, timeout=15)
    cambio.raise_for_status()
    return uid


class FirebaseAuthentication(authentication.BaseAuthentication):
    """Autenticación de DRF: 'Authorization: Bearer <ID token de Firebase>'."""

    keyword = "Bearer"

    def authenticate(self, request):
        cabecera = authentication.get_authorization_header(request).decode()
        partes = cabecera.split()
        if len(partes) != 2 or partes[0] != self.keyword:
            return None
        try:
            datos = verificar_token(partes[1])
        except Exception:
            raise exceptions.AuthenticationFailed(
                "Tu sesión expiró o no es válida. Vuelve a iniciar sesión."
            )

        from apps.usuarios.models import Usuario
        usuario = Usuario.objects.filter(firebase_uid=datos["sub"], is_active=True).first()
        if usuario is None:
            raise exceptions.AuthenticationFailed(
                "Tu cuenta no está habilitada en EasyLit. Pídele a tu gerente que te invite."
            )
        return usuario, datos

    def authenticate_header(self, request):
        return self.keyword
