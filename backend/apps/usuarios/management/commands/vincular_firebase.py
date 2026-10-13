"""
Crea (o actualiza) la cuenta de Firebase de un usuario que ya existe en EasyLit
y la vincula. Sirve para el primer superadmin y los gerentes, que no llegan por
invitación.

    python manage.py vincular_firebase correo@empresa.cl --password "Clave#2026"

Se puede correr desde tu PC apuntando a la base de producción (External Database URL
de Render) con las variables de Firebase definidas.
"""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.usuarios import firebase
from apps.usuarios.models import Usuario


class Command(BaseCommand):
    help = "Crea la cuenta de Firebase de un usuario existente y la vincula."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--password", required=True)

    def handle(self, *args, email, password, **opciones):
        if not firebase.activo():
            raise CommandError("Falta FIREBASE_PROJECT_ID: Firebase no está configurado.")
        usuario = Usuario.objects.filter(email__iexact=email).first()
        if usuario is None:
            raise CommandError(f"No existe ningún usuario con el correo {email}.")
        try:
            validate_password(password, user=usuario)
        except ValidationError as e:
            raise CommandError("La contraseña no cumple las reglas: " + " ".join(e.messages))
        usuario.firebase_uid = firebase.crear_o_actualizar_cuenta(
            usuario.email, password, usuario.nombre_completo,
        )
        # La contraseña de Django no se toca: el panel /admin/ usa su propio login.
        usuario.save(update_fields=["firebase_uid"])
        self.stdout.write(self.style.SUCCESS(
            f"Listo: {usuario.email} ya puede entrar con Firebase (uid {usuario.firebase_uid})."
        ))
