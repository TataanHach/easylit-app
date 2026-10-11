"""Vistas utilitarias transversales."""
from django.conf import settings
from django.http import JsonResponse


def health(request):
    """Endpoint que Render consulta para saber si la api responde."""
    return JsonResponse({"status": "ok", "service": "easylit-api"})


def configuracion(request):
    """
    Reglas de negocio que el frontend necesita conocer (son públicas: la
    pantalla de crear contraseña las usa antes de iniciar sesión). Así viven en
    un solo lugar, settings/.env, en vez de copiadas en el frontend.
    """
    return JsonResponse({
        "iva_porcentaje": round(settings.IVA_TASA * 100, 2),
        "contrasena_min": settings.CONTRASENA_MIN,
        "contrasena_max": settings.CONTRASENA_MAX,
        "archivo_max_mb": settings.ARCHIVO_MAX_MB,
    })
