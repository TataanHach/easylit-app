"""Normalización de textos que se comparan entre registros."""
import re


def normalizar_mandante(valor):
    """
    Nombre del mandante en mayúsculas y sin espacios de más: «codelco », «Codelco»
    y «CODELCO» quedan iguales, así el filtro por empresa no los muestra repetidos.
    """
    return re.sub(r"\s+", " ", valor or "").strip().upper()
