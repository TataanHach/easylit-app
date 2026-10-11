"""
Límite de peso de los archivos que se suben (plantillas y Excel de origen).

Un solo número para todo el backend. El frontend tiene el mismo valor en
src/lib/limites.ts (para avisar antes de subir) y nginx deja pasar un poco más
(frontend/nginx.conf), para que el mensaje claro lo dé esta validación.
"""
from rest_framework import serializers

MAX_MB = 20
MAX_BYTES = MAX_MB * 1024 * 1024


def validar_tamano(archivo):
    """Rechaza el archivo si pesa más de MAX_MB, diciendo cuánto pesa y qué hacer."""
    if archivo.size > MAX_BYTES:
        raise serializers.ValidationError(
            f"El archivo «{archivo.name}» pesa {archivo.size / (1024 * 1024):.1f} MB y el máximo "
            f"es {MAX_MB} MB. Quita hojas o filas que no sean necesarias (o guárdalo sin "
            "imágenes) y vuelve a subirlo."
        )
