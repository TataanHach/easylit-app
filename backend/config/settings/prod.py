"""
Settings de producción.

Sirve tanto para Render (producción real en la nube) como para Docker local.
Las diferencias entre ambos entornos se controlan con variables de entorno, con
valores por defecto pensados para Render. En Docker local se sobreescriben.
"""
import dj_database_url
from decouple import config

from .base import *  # noqa

DEBUG = config("DEBUG", default=False, cast=bool)

SECRET_KEY = config("SECRET_KEY")

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")

# --- Base de datos ---
# DB_SSL=True en Render (conexión cifrada obligatoria).
# DB_SSL=False en Docker local (el PostgreSQL local no usa SSL).
DB_SSL = config("DB_SSL", default=True, cast=bool)
DATABASES = {
    "default": dj_database_url.parse(
        config("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=DB_SSL,
    )
}

# --- Middleware que producción necesita ---
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
MIDDLEWARE.insert(2, "corsheaders.middleware.CorsMiddleware")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- CORS: solo el frontend puede llamar a la API ---
FRONTEND_URL = config("FRONTEND_URL", default="")
CORS_ALLOWED_ORIGINS = [FRONTEND_URL] if FRONTEND_URL else []
CSRF_TRUSTED_ORIGINS = [FRONTEND_URL] if FRONTEND_URL else []

# --- DRF + JWT ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
}

# --- Cola de tareas: Redis ---
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = REDIS_URL

# --- Credenciales de IA ---
GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
IA_MODEL = config("IA_MODEL", default="gemini-flash-latest")

# --- Almacenamiento de archivos ---
# En Render, el disco persistente. En Docker local (u otros), una carpeta local.
# Se controla con MEDIA_ROOT; si no se define, usa la de Render.
MEDIA_ROOT = config("MEDIA_ROOT", default="/opt/render/project/src/media")

# --- Endurecimiento de seguridad para HTTPS ---
# Solo se activa cuando SECURE_SSL=True (Render). En Docker local se apaga,
# porque ahí no hay HTTPS y el redirect dejaría la app inaccesible.
SECURE_SSL = config("SECURE_SSL", default=True, cast=bool)
if SECURE_SSL:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True