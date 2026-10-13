"""
Settings base, común a desarrollo y producción.

Los valores sensibles y los que cambian por entorno (SECRET_KEY, base de datos,
CORS, credenciales de Gemini) se leen de variables de entorno y se afinan en
dev.py / prod.py. Nunca van hardcodeados aquí.
"""
from datetime import timedelta
from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# En desarrollo se puede omitir (usa este valor solo-local, de 50+ caracteres para
# que la firma de las sesiones no avise "clave corta"). prod.py la exige.
SECRET_KEY = config(
    "SECRET_KEY",
    default="dev-solo-local-no-usar-en-produccion-8f3k2m9x7q4w1z6v5b0n",
)
DEBUG = False
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Terceros
    "rest_framework",
    # Lista negra de tokens JWT: al cerrar sesión el refresh deja de servir.
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",

    # Propias
    "apps.organizaciones",
    "apps.usuarios",
    "apps.plantillas",
    "apps.transformaciones",
]

# Configuración de DRF: por defecto todo exige estar autenticado con JWT.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=config("JWT_ACCESS_MINUTOS", default=60, cast=int)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=config("JWT_REFRESH_DIAS", default=7, cast=int)),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Base de datos: SQLite por defecto para poder validar modelos sin infraestructura.
# prod.py la reemplaza por PostgreSQL leyendo DATABASE_URL de Render.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# EL punto clave de este bloque: usuario custom con login por correo.
AUTH_USER_MODEL = "usuarios.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    # 6 a 18 caracteres, con mayúscula, número y carácter especial.
    {"NAME": "apps.usuarios.validadores.ReglasContrasenaValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Integración de IA ---
# Sin GEMINI_API_KEY el sistema usa el modo simulado (heurística local).
IA_PROVIDER = "gemini"
GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
IA_MODEL = config("IA_MODEL", default="models/gemini-3.5-flash-lite")
IA_TIMEOUT_SEGUNDOS = config("IA_TIMEOUT_SEGUNDOS", default=60, cast=int)
# Tope de textos distintos de tablas que se mandan en un "Limpiar con IA" (cuota).
IA_MAX_TEXTOS_TABLA = config("IA_MAX_TEXTOS_TABLA", default=300, cast=int)

# --- Reglas de negocio (el frontend las lee de /api/config/) ---
IVA_TASA = config("IVA_TASA", default=0.19, cast=float)          # 19% en Chile
CONTRASENA_MIN = config("CONTRASENA_MIN", default=6, cast=int)
CONTRASENA_MAX = config("CONTRASENA_MAX", default=18, cast=int)
ARCHIVO_MAX_MB = config("ARCHIVO_MAX_MB", default=20, cast=int)  # nginx.conf deja pasar un poco más
INVITACION_DIAS_VIGENCIA = config("INVITACION_DIAS_VIGENCIA", default=7, cast=int)

# --- Autenticación con Firebase (opcional) ---
# Con FIREBASE_PROJECT_ID, el login lo hace Firebase y Django verifica su token.
# Sin él, se usa el login propio con JWT (desarrollo local).
FIREBASE_PROJECT_ID = config("FIREBASE_PROJECT_ID", default="")
# JSON de la cuenta de servicio (para crear las cuentas de los invitados).
FIREBASE_CREDENCIALES = config("FIREBASE_CREDENCIALES", default="")
if FIREBASE_PROJECT_ID:
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = (
        "apps.usuarios.firebase.FirebaseAuthentication",
    )