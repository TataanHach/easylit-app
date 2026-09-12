"""
Serializers de autenticación.

Traducen entre el JSON que viaja por la API y los modelos. Aquí vive la validación
de entrada: formato de correo, coincidencia de contraseñas, vigencia del token de
invitación. La lógica de negocio (crear invitación, consumir token) va en las
vistas; esto solo valida y da forma a los datos.
"""
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.organizaciones.models import Organizacion
from apps.usuarios.models import Invitacion, Rol, Usuario


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

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Metemos el rol dentro del token para que el frontend sepa qué mostrar
        # sin una llamada extra. No metemos nada sensible.
        token["rol"] = user.rol
        token["nombre"] = user.nombre_completo
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["usuario"] = UsuarioSerializer(self.user).data
        return data


class EstadoCorreoSerializer(serializers.Serializer):
    """
    Entrada del paso previo al login: dado un correo, decir si el usuario existe
    y si ya tiene contraseña. Así el frontend sabe si mostrar "ingresa tu clave"
    o "crea tu clave" (primer ingreso).
    """
    email = serializers.EmailField()


class InvitarUsuarioSerializer(serializers.Serializer):
    """
    Lo que el gerente envía para dar de alta a un trabajador. Solo el correo y el
    nombre son obligatorios; el trabajador completará su RUT y teléfono al crear
    su contraseña.
    """
    email = serializers.EmailField()
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


class CrearContrasenaSerializer(serializers.Serializer):
    """
    Primer ingreso: el trabajador llega con el token de la invitación y define su
    contraseña. Opcionalmente completa su RUT y teléfono.
    """
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)
    rut = serializers.CharField(max_length=12, required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Las contraseñas no coinciden."})

        # Localizar la invitación y comprobar que siga vigente.
        try:
            invitacion = Invitacion.objects.select_related("usuario").get(token=attrs["token"])
        except Invitacion.DoesNotExist:
            raise serializers.ValidationError({"token": "Invitación no encontrada."})

        if not invitacion.vigente:
            raise serializers.ValidationError({"token": "La invitación expiró o ya fue usada."})

        # Validar la fuerza de la contraseña con las reglas de Django.
        validate_password(attrs["password"], user=invitacion.usuario)

        attrs["invitacion"] = invitacion
        return attrs
