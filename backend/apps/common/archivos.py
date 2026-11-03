"""
Validación de los archivos que se suben (plantillas y Excel de origen).

El peso máximo se configura con ARCHIVO_MAX_MB (settings/.env). El frontend lo
lee de /api/config/ para avisar antes de subir; si igual llega uno más pesado,
esta validación lo rechaza con un mensaje claro.

Solo se aceptan .xlsx y .csv. Un CSV se convierte aquí mismo a .xlsx: todo el
resto del sistema (limpieza, generación) lee el archivo con openpyxl.
"""
import csv
import io
import os
import shutil
import tempfile
import zipfile

from django.conf import settings
from django.core.files.base import ContentFile
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


EXTENSIONES_PLANILLA = (".xlsx", ".csv")


def _es_xlsx(datos):
    """Un .xlsx de verdad es un ZIP con el libro adentro (no un archivo renombrado)."""
    try:
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            return "xl/workbook.xml" in z.namelist()
    except zipfile.BadZipFile:
        return False


def _texto_csv(datos):
    """Texto del CSV (UTF-8 o, si no, la codificación de Excel en Windows), o None si es binario."""
    if b"\x00" in datos[:4096]:
        return None
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return None


def _csv_a_xlsx(texto, nombre_base):
    """Convierte el CSV a un libro de Excel con una sola hoja. Devuelve los bytes o None si no trae datos."""
    from openpyxl import Workbook

    muestra = texto[:8192]
    try:
        separador = csv.Sniffer().sniff(muestra, delimiters=";,\t|").delimiter
    except csv.Error:
        separador = ";" if muestra.count(";") > muestra.count(",") else ","
    filas = [f for f in csv.reader(io.StringIO(texto), delimiter=separador)]
    if not any(c.strip() for f in filas for c in f):
        return None
    wb = Workbook()
    ws = wb.active
    ws.title = (nombre_base or "Datos")[:31].translate(str.maketrans("[]:*?/\\", "       ")).strip() or "Datos"
    for f in filas:
        ws.append([c.strip() if c.strip() else None for c in f])
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def validar_planilla(archivo):
    """
    Revisa que el archivo sea un .xlsx o .csv válido, no vacío y no muy pesado.
    Devuelve el archivo a guardar: el mismo si es .xlsx, o un .xlsx nuevo si era CSV.
    """
    nombre = archivo.name
    base, ext = os.path.splitext(nombre)
    ext = ext.lower()
    if ext not in EXTENSIONES_PLANILLA:
        extra = (" Si lo tienes en .xls o .xlsm, ábrelo en Excel y usa «Guardar como» → "
                 "«Libro de Excel (.xlsx)»." if ext in (".xls", ".xlsm", ".xlsb") else "")
        raise serializers.ValidationError(
            f"«{nombre}» no es un archivo .xlsx ni .csv. Sube el archivo en uno de esos formatos.{extra}"
        )
    if archivo.size == 0:
        raise serializers.ValidationError(
            f"«{nombre}» está vacío. Revisa que se haya guardado bien y vuelve a subirlo."
        )
    validar_tamano(archivo)

    archivo.seek(0)
    datos = archivo.read()
    archivo.seek(0)
    if ext == ".xlsx":
        if not _es_xlsx(datos):
            raise serializers.ValidationError(
                f"«{nombre}» no es un Excel válido: puede estar dañado o ser otro tipo de archivo "
                "con el nombre cambiado. Ábrelo en Excel, guárdalo como .xlsx y vuelve a subirlo."
            )
        return archivo

    texto = _texto_csv(datos)
    if texto is None:
        raise serializers.ValidationError(
            f"«{nombre}» no es un CSV válido: no es texto. Si es un Excel, súbelo como .xlsx."
        )
    convertido = _csv_a_xlsx(texto, os.path.basename(base))
    if convertido is None:
        raise serializers.ValidationError(
            f"«{nombre}» no tiene datos. Revisa que se haya guardado bien y vuelve a subirlo."
        )
    return ContentFile(convertido, name=f"{os.path.basename(base)}.xlsx")


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
