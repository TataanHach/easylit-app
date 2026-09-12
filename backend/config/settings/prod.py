"""
Settings de producción (Render).

Todo lo sensible o dependiente del entorno se lee de variables de entorno que
Render inyecta según el render.yaml. Nada secreto vive en el código.
"""
import dj_database_url
from decouple import config

from .base import *  # noqa

DEBUG = False

SECRET_KEY = config("SECRET_KEY")

# Dominio(s) del backend en Render, separados por coma.
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")

# --- Base de datos: PostgreSQL de Render ---
DATABASES = {
    "default": dj_database_url.parse(
        config("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=True,
    )
}

# --- Middleware que producción necesita ---
# rest_framework y corsheaders ya están en INSTALLED_APPS (base.py); aquí solo
# añadimos su middleware, sin volver a registrar las apps (eso duplicaba y
# rompía el worker con "Application labels aren't unique").
# WhiteNoise sirve los estáticos del admin de Django sin un servidor aparte.
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

# --- DRF + JWT (se configura en detalle en el bloque de autenticación) ---
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

# --- Cola de tareas: Redis de Render ---
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# --- Credenciales de IA ---
GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
IA_MODEL = config("IA_MODEL", default="gemini-flash-latest")

# --- Almacenamiento de archivos: disco persistente de Render ---
# Los archivos subidos y generados van al disco montado (ver render.yaml), para
# que sobrevivan a los reinicios del servicio.
MEDIA_ROOT = "/opt/render/project/src/media"

# --- Endurecimiento de seguridad para HTTPS ---
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True