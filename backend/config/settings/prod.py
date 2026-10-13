"""
Settings de producción.

Sirve tanto para Render (producción real en la nube) como para Docker local.
Las diferencias entre ambos entornos se controlan con variables de entorno, con
valores por defecto pensados para Render. En Docker local se sobreescriben.
"""
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from decouple import config

from .base import *  # noqa

DEBUG = config("DEBUG", default=False, cast=bool)

SECRET_KEY = config("SECRET_KEY")

ALLOWED_HOSTS = [h for h in config("ALLOWED_HOSTS", default="").split(",") if h]
# Render informa su propio dominio (easylit-api.onrender.com): se agrega solo.
if config("RENDER_EXTERNAL_HOSTNAME", default=""):
    ALLOWED_HOSTS.append(config("RENDER_EXTERNAL_HOSTNAME"))

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

# Archivos subidos (Excel de origen, plantillas, documentos generados):
#   - Con R2_BUCKET definido → Cloudflare R2 (compatible con S3). La API y el
#     worker leen y escriben en el mismo lugar, sin disco compartido.
#   - Sin R2 → disco local (solo Docker local). En Render NO: su disco se borra
#     en cada reinicio o despliegue (el plan gratis no tiene disco persistente),
#     así que ahí R2 es obligatorio.
R2_BUCKET = config("R2_BUCKET", default="")
if not R2_BUCKET and config("RENDER", default=False, cast=bool):
    raise ImproperlyConfigured(
        "En Render falta R2_BUCKET: sin Cloudflare R2 los archivos se perderían "
        "en cada reinicio. Configura las variables R2_* (ver DESPLIEGUE.md)."
    )
if R2_BUCKET:
    _ALMACEN = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": R2_BUCKET,
            "endpoint_url": config("R2_ENDPOINT"),          # https://<cuenta>.r2.cloudflarestorage.com
            "access_key": config("R2_ACCESS_KEY_ID"),
            "secret_key": config("R2_SECRET_ACCESS_KEY"),
            "region_name": "auto",
            "signature_version": "s3v4",
            "default_acl": None,          # el bucket es privado
            "file_overwrite": False,      # nunca pisar un archivo con el mismo nombre
            "querystring_auth": True,     # enlaces firmados y temporales
        },
    }
else:
    _ALMACEN = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": _ALMACEN,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- CORS: solo el frontend puede llamar a la API ---
FRONTEND_URL = config("FRONTEND_URL", default="")
CORS_ALLOWED_ORIGINS = [FRONTEND_URL] if FRONTEND_URL else []
CSRF_TRUSTED_ORIGINS = [FRONTEND_URL] if FRONTEND_URL else []

# --- DRF + JWT ---
REST_FRAMEWORK = {
    # Firebase si está configurado (FIREBASE_PROJECT_ID); si no, el login propio con JWT.
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.usuarios.firebase.FirebaseAuthentication"
        if FIREBASE_PROJECT_ID else "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
}

# --- Cola de tareas: Redis ---
# Obligatoria: sin Redis no hay cola de tareas, y es mejor que el servidor no
# arranque a que arranque apuntando a un localhost que no existe.
REDIS_URL = config("REDIS_URL")
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = REDIS_URL

# La IA (GEMINI_API_KEY, IA_MODEL) y las reglas de negocio se leen en base.py.

# --- Carpeta de archivos sin R2 (solo Docker local) ---
MEDIA_ROOT = config("MEDIA_ROOT", default=str(BASE_DIR / "media"))

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