"""
Límite de peso de los archivos que se suben (plantillas y Excel de origen).

Se configura con ARCHIVO_MAX_MB (settings/.env). El frontend lo lee de
/api/config/ para avisar antes de subir; si igual llega uno más pesado, esta
validación lo rechaza con un mensaje claro.
"""
import os
import shutil
import tempfile

from django.conf import settings
from rest_framework import serializers

MAX_MB = settings.ARCHIVO_MAX_MB
MAX_BYTES = MAX_MB * 1024 * 1024


def validar_tamano(archivo):
    """Rechaza el archivo si pesa más de MAX_MB, diciendo cuánto pesa y qué hacer."""
    if archivo.size > MAX_BYTES:
        raise serializers.ValidationError(
            f"El archivo «{archivo.name}» pesa {archivo.size / (1024 * 1024):.1f} MB y el máximo "
            f"es {MAX_MB} MB. Quita hojas o filas que no sean necesarias (o guárdalo sin "
            "imágenes) y vuelve a subirlo."
        )


# Copias locales de archivos guardados en la nube (R2), para abrirlos con
# openpyxl/pandas, que necesitan una ruta en disco.
_CACHE_LOCAL = os.path.join(tempfile.gettempdir(), "easylit_archivos")


def ruta_local(archivo):
    """
    Ruta en disco de un archivo subido (FileField), para abrirlo con openpyxl o
    pandas. En local (carpeta media/) es su ruta de siempre. Con almacenamiento
    en la nube (Cloudflare R2) lo descarga una vez a una carpeta temporal y
    reutiliza esa copia: los archivos subidos no cambian (cada subida tiene un
    nombre único), así que la copia nunca queda desactualizada.
    """
    try:
        return archivo.path
    except NotImplementedError:
        pass  # El almacenamiento no es un disco local (R2/S3).
    destino = os.path.join(_CACHE_LOCAL, archivo.name.replace("/", os.sep))
    if not os.path.exists(destino):
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        temporal = destino + ".descargando"
        with archivo.storage.open(archivo.name, "rb") as origen, open(temporal, "wb") as salida:
            shutil.copyfileobj(origen, salida)
        os.replace(temporal, destino)  # atómico: nunca queda una copia a medias
    return destino
