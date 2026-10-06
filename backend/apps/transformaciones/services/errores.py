"""
Traducción de errores técnicos a mensajes para el usuario.

El usuario no debe ver un stacktrace ni un "KeyError: 'B'". Cada mensaje dice
QUÉ falló, POR QUÉ (si se sabe) y QUÉ HACER. El detalle técnico va a la
bitácora para quien tenga que depurar.
"""
import zipfile


class ErrorUsuario(Exception):
    """Error con un mensaje ya pensado para el usuario (se muestra tal cual)."""


def mensaje_amigable(exc, etapa):
    """
    Devuelve un texto legible para `exc`. `etapa` es "procesar" (lectura,
    limpieza y mapeo del origen) o "generar" (rellenar la plantilla).
    """
    if isinstance(exc, ErrorUsuario):
        return str(exc)

    texto = str(exc)
    bajo = texto.lower()
    archivo = "el archivo de la licitación" if etapa == "procesar" else "la plantilla"

    if isinstance(exc, zipfile.BadZipFile) or "not a zip file" in bajo or "invalidfileexception" in type(exc).__name__.lower():
        return (
            f"No se pudo abrir {archivo}: no es un Excel válido o está dañado. "
            "Ábrelo en Excel, guárdalo como .xlsx y vuelve a subirlo."
        )
    if isinstance(exc, FileNotFoundError):
        return (
            f"No se encontró {archivo} en el servidor. Puede que se haya borrado. "
            "Vuelve a subirlo e intenta de nuevo."
        )
    if isinstance(exc, PermissionError):
        return (
            f"El servidor no pudo leer {archivo} porque está bloqueado. "
            "Ciérralo si lo tienes abierto en Excel y vuelve a intentarlo."
        )
    if isinstance(exc, (UnicodeDecodeError,)) or "codec" in bajo:
        return (
            f"No se pudo leer el texto de {archivo} (codificación desconocida). "
            "Si es un CSV, guárdalo como .xlsx o como CSV UTF-8 y vuelve a subirlo."
        )
    if isinstance(exc, MemoryError):
        return (
            f"{archivo.capitalize()} es demasiado grande para procesarlo. "
            "Quita hojas o filas que no sean necesarias y vuelve a subirlo."
        )

    accion = "procesar la licitación" if etapa == "procesar" else "generar el documento"
    return (
        f"Ocurrió un error inesperado al {accion}. Intenta de nuevo; si se repite, "
        f"avisa al administrador con este detalle: {texto[:200]}"
    )
