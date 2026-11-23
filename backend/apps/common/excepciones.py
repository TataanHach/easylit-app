"""
Manejador de errores de la API.

DRF responde «No <Modelo> matches the given query.» cuando no encuentra un
registro, en inglés y con el nombre interno del modelo. Aquí se cambia por un
mensaje en palabras simples; el resto de los errores pasa sin cambios.
"""
from django.http import Http404
from rest_framework.exceptions import NotFound
from rest_framework.views import exception_handler

MENSAJE_NO_ENCONTRADO = (
    "No se encontró lo que buscas. Puede que alguien lo haya eliminado; recarga la página."
)


def manejar_excepcion(exc, context):
    if isinstance(exc, Http404):
        exc = NotFound(MENSAJE_NO_ENCONTRADO)
    return exception_handler(exc, context)
