"""
Reglas de contraseña de EasyLit.

Se registran en AUTH_PASSWORD_VALIDATORS, así que aplican en todo lugar que
use `validate_password` (crear contraseña desde una invitación, admin, etc.).
La misma regla está en el frontend (src/lib/contrasena.ts) para avisar en vivo.
"""
from django.core.exceptions import ValidationError

MIN_LARGO = 6
MAX_LARGO = 18


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
