"""Settings de desarrollo."""
from decouple import config
from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# CORS: en dev permitimos el frontend de Vite.
MIDDLEWARE.insert(1, "corsheaders.middleware.CorsMiddleware")
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# --- Cola de tareas: Redis local (Docker) ---
REDIS_URL = "redis://localhost:6379/0"
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# --- IA: leer la clave de Gemini del archivo .env ---
# Si el .env tiene GEMINI_API_KEY, se usa Gemini real. Si está vacía, el sistema
# cae al modo simulado (heurística local) automáticamente.
GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
IA_MODEL = config("IA_MODEL", default="gemini-flash-latest")