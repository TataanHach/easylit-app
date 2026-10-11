"""
Serializers de autenticación.

Traducen entre el JSON que viaja por la API y los modelos. Aquí vive la validación
de entrada: formato de correo, coincidencia de contraseñas, vigencia del token de
invitación. La lógica de negocio (crear invitación, consumir token) va en las
vistas; esto solo valida y da forma a los datos.
"""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.organizaciones.models import Organizacion
from apps.usuarios.models import Invitacion, Rol, Usuario
from apps.usuarios.validadores import normalizar_rut


def _validar_rut(value):
    """RUT opcional: vacío se acepta; si viene, debe ser válido."""
    if not value:
        return value
    try:
        return normalizar_rut(value)
    except DjangoValidationError as e:
        raise serializers.ValidationError(e.messages)


class UsuarioSerializer(serializers.ModelSerializer):
    """Representación pública de un usuario. Nunca expone la contraseña."""

    organizacion_nombre = serializers.CharField(
        source="organizacion.nombre", read_only=True, default=None
    )

    class Meta:
        model = Usuario
        fields = (
            "id", "email", "nombre_completo", "rut", "telefono",
            "rol", "organizacion", "organizacion_nombre",
            "necesita_crear_contrasena",
        )
        read_only_fields = ("id", "rol", "organizacion", "necesita_crear_contrasena")


class LoginSerializer(TokenObtainPairSerializer):
    """
    Login por correo + contraseña que devuelve el par de tokens JWT y, además,
    los datos del usuario, para que el frontend no tenga que pedirlos aparte.
    """

    default_error_messages = {
        "no_active_account": "Correo o contraseña incorrectos. Revisa que estén bien "
                             "escritos (las mayúsculas en la contraseña importan).",
    }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Metemos el rol dentro del token para que el frontend sepa qué mostrar
        # sin una llamada extra. No metemos nada sensible.
        token["rol"] = user.rol
        token["nombre"] = user.nombre_completo
        return token

    def validate(self, attrs):
        # El correo se guarda en minúsculas: "Juan@Empresa.cl" debe entrar igual.
        attrs[self.username_field] = attrs[self.username_field].lower()
        data = super().validate(attrs)
        data["usuario"] = UsuarioSerializer(self.user).data
        return data


class EstadoCorreoSerializer(serializers.Serializer):
    """
    Entrada del paso previo al login: dado un correo, decir si el usuario existe
    y si ya tiene contraseña. Así el frontend sabe si mostrar "ingresa tu clave"
    o "crea tu clave" (primer ingreso).
    """
    email = serializers.EmailField(max_length=254)


class InvitarUsuarioSerializer(serializers.Serializer):
    """
    Lo que el gerente envía para dar de alta a un trabajador. Solo el correo y el
    nombre son obligatorios; el trabajador completará su RUT y teléfono al crear
    su contraseña.
    """
    email = serializers.EmailField(max_length=254)
    nombre_completo = serializers.CharField(max_length=200)
    rut = serializers.CharField(max_length=12, required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True)
    # El gerente solo puede crear TRABAJADOR. Un gerente no crea otros gerentes;
    # eso queda para el superadmin. Por eso el rol no se acepta como entrada.

    def validate_email(self, value):
        value = value.lower()
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este correo.")
        return value

    def validate_rut(self, value):
        return _validar_rut(value)


class CrearContrasenaSerializer(serializers.Serializer):
    """
    Primer ingreso: el trabajador llega con el token de la invitación y define su
    contraseña. Opcionalmente completa su RUT y teléfono.
    """
    token = serializers.CharField(max_length=64)
    # Sin recortar espacios: en una contraseña pueden ser intencionales.
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, trim_whitespace=False)
    rut = serializers.CharField(max_length=12, required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate_rut(self, value):
        return _validar_rut(value)

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Las contraseñas no coinciden. Escribe la misma en los dos campos."})

        # Localizar la invitación y comprobar que siga vigente.
        try:
            invitacion = Invitacion.objects.select_related("usuario").get(token=attrs["token"])
        except Invitacion.DoesNotExist:
            raise serializers.ValidationError({
                "token": "El código de invitación no existe. Cópialo completo desde el "
                         "correo de invitación o pide uno nuevo a tu gerente."
            })

        if not invitacion.vigente:
            raise serializers.ValidationError({
                "token": "La invitación expiró o ya fue usada. Si ya creaste tu contraseña, "
                         "inicia sesión; si no, pide una invitación nueva a tu gerente."
            })

        # Validar la contraseña con las reglas configuradas (apps/usuarios/validadores.py).
        try:
            validate_password(attrs["password"], user=invitacion.usuario)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})

        attrs["invitacion"] = invitacion
        return attrs
