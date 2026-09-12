"""Vistas utilitarias transversales."""
from django.http import JsonResponse


def health(request):
    """Endpoint que Render consulta para saber si la api responde."""
    return JsonResponse({"status": "ok", "service": "easylit-api"})
