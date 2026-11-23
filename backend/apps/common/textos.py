"""Normalización y validación de textos que escriben los usuarios."""
import re

# Caracteres aceptados además de letras (con tildes y ñ), números y espacios.
# La misma regla está en el frontend (src/lib/validar.ts).
SIGNOS_TEXTO = ".,-()/&'’°º"       # nombre de plantilla, mandante, sector
SIGNOS_PERSONA = ".'’-"            # nombres de personas (sin números)
AYUDA_TEXTO = "Usa solo letras, números, espacios y . , - ( ) / & ' °"
AYUDA_PERSONA = "Usa solo letras, espacios y . ' -"

# Correo: letras, números y . _ - + antes de la @, y un dominio con punto.
FORMATO_CORREO = re.compile(r"[A-Za-z0-9._+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def _no_permitidos(valor, permitido):
    """Caracteres de `valor` que no cumplen `permitido`, sin repetir y en orden."""
    vistos = []
    for c in valor or "":
        if not permitido(c) and c not in vistos:
            vistos.append(c)
    return vistos


def problema_caracteres(valor, *, persona=False):
    """
    "" si el texto solo tiene caracteres aceptados; si no, el mensaje que dice
    cuáles sobran (ej. «# $») y qué se puede usar.
    """
    if persona:
        malos = _no_permitidos(valor, lambda c: c.isalpha() or c.isspace() or c in SIGNOS_PERSONA)
        ayuda = AYUDA_PERSONA
    else:
        malos = _no_permitidos(valor, lambda c: c.isalnum() or c.isspace() or c in SIGNOS_TEXTO)
        ayuda = AYUDA_TEXTO
    if not malos:
        return ""
    return f"Tiene caracteres que no se aceptan: {' '.join(malos)}. {ayuda}."


def problema_correo(valor):
    """"" si el correo tiene un formato aceptado; si no, qué corregir."""
    if FORMATO_CORREO.fullmatch(valor or ""):
        return ""
    return ("El correo tiene caracteres que no se aceptan. Usa solo letras, números y "
            ". _ - + antes de la @, como nombre@empresa.cl.")


def normalizar_mandante(valor):
    """
    Nombre del mandante en mayúsculas y sin espacios de más: «codelco », «Codelco»
    y «CODELCO» quedan iguales, así el filtro por empresa no los muestra repetidos.
    """
    return re.sub(r"\s+", " ", valor or "").strip().upper()
