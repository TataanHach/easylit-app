"""
Reglas de contraseña de EasyLit.

Se registran en AUTH_PASSWORD_VALIDATORS, así que aplican en todo lugar que
use `validate_password` (crear contraseña desde una invitación, admin, etc.).
La misma regla está en el frontend (src/lib/contrasena.ts) para avisar en vivo.
"""
from django.core.exceptions import ValidationError

from django.conf import settings

# Se configuran con CONTRASENA_MIN / CONTRASENA_MAX (settings/.env).
MIN_LARGO = settings.CONTRASENA_MIN
MAX_LARGO = settings.CONTRASENA_MAX


def _es_especial(c):
    return not c.isalnum() and not c.isspace()


class ReglasContrasenaValidator:
    """6 a 18 caracteres, con al menos una mayúscula, un número y un carácter especial."""

    def validate(self, password, user=None):
        errores = []
        if len(password) < MIN_LARGO:
            errores.append(f"Debe tener al menos {MIN_LARGO} caracteres (tiene {len(password)}).")
        if len(password) > MAX_LARGO:
            errores.append(f"Debe tener como máximo {MAX_LARGO} caracteres (tiene {len(password)}).")
        if not any(c.isupper() for c in password):
            errores.append("Debe incluir al menos una letra mayúscula (A-Z).")
        if not any(c.isdigit() for c in password):
            errores.append("Debe incluir al menos un número (0-9).")
        if not any(_es_especial(c) for c in password):
            errores.append("Debe incluir al menos un carácter especial, por ejemplo ! @ # $ % & * ? -")
        if errores:
            raise ValidationError(errores, code="password_reglas")

    def get_help_text(self):
        return (
            f"La contraseña debe tener entre {MIN_LARGO} y {MAX_LARGO} caracteres, con al "
            "menos una mayúscula, un número y un carácter especial."
        )


def normalizar_rut(valor):
    """
    Valida un RUT chileno y lo devuelve normalizado sin puntos ni guion
    ("12.345.678-5" → "123456785"). Lanza ValidationError con el motivo si no
    es válido. Es la misma regla que src/lib/rut.ts en el frontend.
    """
    limpio = valor.replace(".", "").replace("-", "").replace(" ", "").upper()
    cuerpo, dv = limpio[:-1], limpio[-1:]
    if len(limpio) < 2 or not cuerpo.isdigit():
        raise ValidationError("El RUT debe tener el formato 12.345.678-9.")

    suma, mult = 0, 2
    for digito in reversed(cuerpo):
        suma += int(digito) * mult
        mult = 2 if mult == 7 else mult + 1
    resto = 11 - (suma % 11)
    esperado = {11: "0", 10: "K"}.get(resto, str(resto))
    if dv != esperado:
        raise ValidationError("El dígito verificador del RUT no corresponde. Revisa que esté bien escrito.")
    return limpio
