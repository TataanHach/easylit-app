"""
Vistas de autenticación.

Cada vista es un endpoint. La lógica de negocio del flujo de invitación vive aquí:
crear el usuario sin contraseña + su token (invitar), y consumir el token
fijando la contraseña (primer ingreso). Todo lo que cambia estado deja además
un registro en la bitácora cuando corresponde.
"""
import secrets
from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.usuarios.models import Invitacion, Rol, Usuario

from .permissions import EsGerenteOSuperadmin
from .serializers import (
    CrearContrasenaSerializer,
    EstadoCorreoSerializer,
    InvitarUsuarioSerializer,
    LoginSerializer,
    UsuarioSerializer,
)

# Cuántos días vale una invitación antes de expirar.
DIAS_VIGENCIA_INVITACION = 7


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/  → { access, refresh, usuario }"""
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]


class EstadoCorreoView(APIView):
    """
    POST /api/auth/estado-correo/  → dice cómo continuar según el correo.

    Es el paso previo al login que definiste: si el usuario existe pero no tiene
    contraseña, el frontend lo manda a "crear contraseña"; si ya tiene, a login.
    Por seguridad no revela datos: solo 'existe' y 'necesita_contrasena'.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EstadoCorreoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()

        usuario = Usuario.objects.filter(email=email, is_active=True).first()
        if not usuario:
            return Response({"existe": False, "necesita_contrasena": False})

        return Response({
            "existe": True,
            "necesita_contrasena": usuario.necesita_crear_contrasena,
        })


class InvitarUsuarioView(APIView):
    """
    POST /api/auth/invitar/  (solo gerente/superadmin)

    Da de alta a un trabajador: crea el usuario SIN contraseña, dentro de la
    organización de quien invita, y genera el token de invitación. En producción,
    el worker enviará el correo con el enlace; aquí devolvemos el token para poder
    probar el flujo completo.
    """
    permission_classes = [IsAuthenticated, EsGerenteOSuperadmin]

    def post(self, request):
        serializer = InvitarUsuarioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        # El trabajador hereda la organización de quien lo invita. Si es el
        # superadmin (sin organización), debe indicarse aparte; para el MVP el
        # que invita es el gerente, que sí tiene organización.
        organizacion = request.user.organizacion
        if organizacion is None:
            return Response(
                {"detail": "El superadmin debe crear usuarios desde el panel de administración."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Crear el usuario sin contraseña utilizable.
        usuario = Usuario.objects.create_user(
            email=datos["email"],
            password=None,
            nombre_completo=datos["nombre_completo"],
            rut=datos.get("rut", ""),
            telefono=datos.get("telefono", ""),
            rol=Rol.TRABAJADOR,
            organizacion=organizacion,
        )

        invitacion = Invitacion.objects.create(
            usuario=usuario,
            token=secrets.token_urlsafe(32),
            invitado_por=request.user,
            expira=timezone.now() + timedelta(days=DIAS_VIGENCIA_INVITACION),
        )

        return Response(
            {
                "usuario": UsuarioSerializer(usuario).data,
                # En producción esto NO se devuelve: viaja por correo. En dev sí,
                # para poder probar el primer ingreso sin servidor de correo.
                "token_invitacion": invitacion.token,
                "expira": invitacion.expira,
            },
            status=status.HTTP_201_CREATED,
        )


class CrearContrasenaView(APIView):
    """
    POST /api/auth/crear-contrasena/  (primer ingreso, sin autenticación)

    El trabajador llega con el token de la invitación, define su contraseña y
    queda listo para iniciar sesión. Consume el token para que no se reutilice.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CrearContrasenaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        invitacion = datos["invitacion"]
        usuario = invitacion.usuario

        # Fijar la contraseña y completar datos opcionales.
        usuario.set_password(datos["password"])
        if datos.get("rut"):
            usuario.rut = datos["rut"]
        if datos.get("telefono"):
            usuario.telefono = datos["telefono"]
        usuario.save()

        # Consumir la invitación.
        invitacion.usada_en = timezone.now()
        invitacion.save(update_fields=["usada_en"])

        # Devolver tokens ya iniciados, para que entre directo tras crear la clave.
        refresh = RefreshToken.for_user(usuario)
        refresh["rol"] = usuario.rol
        refresh["nombre"] = usuario.nombre_completo

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "usuario": UsuarioSerializer(usuario).data,
        })


class PerfilView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /api/auth/perfil/  → datos del usuario autenticado.

    Sirve al frontend para saber quién está logueado tras recargar la página.
    """
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
