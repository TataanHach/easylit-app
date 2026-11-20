"""
Límites de intentos en los endpoints públicos de autenticación.

Frenan a quien prueba muchas veces seguidas: contraseñas en el login, códigos
de invitación en "crear contraseña" o correos en "estado-correo" (para averiguar
quién tiene cuenta). Los máximos se cambian con variables de entorno, ver
DEFAULT_THROTTLE_RATES en config/settings/base.py.

En producción el login con contraseña lo hace Firebase, que tiene su propio
bloqueo; estos límites cubren lo que pasa por nuestra API.

Los contadores viven en la caché de Django (en memoria del proceso). Con el
único proceso de gunicorn de Render basta; si se reinicia, parten de cero.
"""
import math

from rest_framework import exceptions
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle


class DemasiadosIntentos(exceptions.Throttled):
    """429 con un mensaje en español y la espera en minutos (Retry-After en segundos)."""

    def __init__(self, wait=None):
        minutos = max(1, math.ceil((wait or 60) / 60))
        texto = (
            "Hiciste demasiados intentos seguidos. Por seguridad, espera "
            f"{minutos} minuto{'s' if minutos != 1 else ''} y vuelve a intentarlo."
        )
        super().__init__(wait=None, detail=texto)   # sin la frase en inglés de DRF
        self.wait = math.ceil(wait) if wait else None


class PorCuentaThrottle(SimpleRateThrottle):
    """
    Cuenta los intentos por correo, no por IP: frena a quien prueba contraseñas
    de una misma cuenta desde muchas IP distintas.
    """
    scope = "login_cuenta"

    def get_cache_key(self, request, view):
        correo = str(request.data.get("email", "")).strip().lower()
        if not correo:
            return None   # sin correo no hay a quién proteger (el serializer lo rechaza)
        return self.cache_format % {"scope": self.scope, "ident": correo}


class LimiteDeIntentos:
    """
    Mixin para las vistas públicas: límite por IP según `throttle_scope`
    (y las clases extra de `throttles_extra`), con el aviso en español.
    """
    throttles_extra = ()

    def get_throttles(self):
        return [ScopedRateThrottle(), *(clase() for clase in self.throttles_extra)]

    def throttled(self, request, wait):
        raise DemasiadosIntentos(wait)
