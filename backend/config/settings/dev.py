"""Settings de desarrollo."""
from decouple import Csv, config
from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# CORS: en dev permitimos el frontend de Vite.
MIDDLEWARE.insert(1, "corsheaders.middleware.CorsMiddleware")
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS", default="http://localhost:5173,http://127.0.0.1:5173", cast=Csv()
)

# --- Cola de tareas: Redis local ---
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# La IA (GEMINI_API_KEY, IA_MODEL) y las reglas de negocio se leen en base.py.