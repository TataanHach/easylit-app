"""
Vistas de autenticación.

Cada vista es un endpoint. La lógica de negocio del flujo de invitación vive aquí:
crear el usuario sin contraseña + su token (invitar), y consumir el token
fijando la contraseña (primer ingreso). Todo lo que cambia estado deja además
un registro en la bitácora cuando corresponde.
"""
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.usuarios import firebase
from apps.usuarios.models import Invitacion, Rol, Usuario

from .limites import LimiteDeIntentos, PorCuentaThrottle
from .permissions import EsGerenteOSuperadmin
from .serializers import (
    CrearContrasenaSerializer,
    EstadoCorreoSerializer,
    InvitarUsuarioSerializer,
    LoginSerializer,
    MiembroEquipoSerializer,
    UsuarioSerializer,
)


class LoginView(LimiteDeIntentos, TokenObtainPairView):
    """
    POST /api/auth/login/  → { access, refresh, usuario }

    Con límite de intentos por IP y por cuenta (ver limites.py).
    """
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_scope = "login"
    throttles_extra = (PorCuentaThrottle,)


class LogoutView(APIView):
    """
    POST /api/auth/logout/  { refresh }  → invalida el refresh token.

    Sin esto, cerrar sesión solo borraba el token del navegador y una copia del
    token seguía sirviendo para entrar hasta que venciera. AllowAny porque basta
    con tener el refresh: el access puede haber vencido ya.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            RefreshToken(request.data.get("refresh", "")).blacklist()
        except TokenError:
            pass  # Ya vencido o inválido: la sesión ya no sirve, no hay nada que hacer.
        return Response(status=status.HTTP_204_NO_CONTENT)


class EstadoCorreoView(LimiteDeIntentos, APIView):
    """
    POST /api/auth/estado-correo/  → dice cómo continuar según el correo.

    Es el paso previo al login que definiste: si el usuario existe pero no tiene
    contraseña, el frontend lo manda a "crear contraseña"; si ya tiene, a login.
    Por seguridad no revela datos: solo 'existe' y 'necesita_contrasena'. El
    límite de intentos frena a quien prueba correos para ver cuáles existen.
    """
    permission_classes = [AllowAny]
    throttle_scope = "estado_correo"

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
    organización de quien invita, y genera el código de invitación. No se envía
    correo: el código vuelve en la respuesta y el gerente se lo hace llegar
    (pantalla Equipo → Copiar mensaje).
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

        # Usuario sin contraseña utilizable + su código, juntos o ninguno.
        with transaction.atomic():
            usuario = Usuario.objects.create_user(
                email=datos["email"],
                password=None,
                nombre_completo=datos["nombre_completo"],
                rut=datos["rut"],
                telefono=datos.get("telefono", ""),
                rol=Rol.TRABAJADOR,
                organizacion=organizacion,
            )
            invitacion = Invitacion.nueva(usuario, request.user)

        return Response(
            {
                "usuario": UsuarioSerializer(usuario).data,
                # Solo lo recibe el gerente que invita (no hay envío de correo).
                "token_invitacion": invitacion.codigo,
                "expira": invitacion.expira,
            },
            status=status.HTTP_201_CREATED,
        )


class EquipoView(generics.ListAPIView):
    """
    GET /api/auth/equipo/  (solo gerente/superadmin)

    Las personas de la organización de quien consulta, con el estado de su acceso
    y, si tienen un código vigente, el código para que el gerente se lo reenvíe.
    Nunca muestra personas de otra organización.
    """
    permission_classes = [IsAuthenticated, EsGerenteOSuperadmin]
    serializer_class = MiembroEquipoSerializer
    pagination_class = None

    def get_queryset(self):
        organizacion = self.request.user.organizacion
        if organizacion is None:
            return Usuario.objects.none()
        return (
            Usuario.objects.filter(organizacion=organizacion)
            .prefetch_related(Prefetch("invitaciones", queryset=Invitacion.objects.order_by("-creada")))
            .order_by("nombre_completo")
        )


class NuevaInvitacionView(APIView):
    """
    POST /api/auth/equipo/<id>/invitacion/  (solo gerente/superadmin)

    Genera un código nuevo para alguien del equipo que aún no activa su cuenta:
    porque el anterior venció, se perdió, o porque lo crearon desde el panel de
    administración. El código anterior deja de servir.
    """
    permission_classes = [IsAuthenticated, EsGerenteOSuperadmin]

    def post(self, request, pk):
        organizacion = request.user.organizacion
        usuario = (
            Usuario.objects.filter(pk=pk, organizacion=organizacion, is_active=True).first()
            if organizacion else None
        )
        if usuario is None:
            return Response(
                {"detail": "Esa persona no está en tu equipo o no tiene el acceso habilitado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not usuario.necesita_crear_contrasena:
            return Response(
                {"detail": "Esta persona ya activó su cuenta: puede entrar con su correo y su contraseña."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitacion = Invitacion.nueva(usuario, request.user)
        return Response(
            {"token_invitacion": invitacion.codigo, "expira": invitacion.expira},
            status=status.HTTP_201_CREATED,
        )


class CrearContrasenaView(LimiteDeIntentos, APIView):
    """
    POST /api/auth/crear-contrasena/  (primer ingreso, sin autenticación)

    El trabajador llega con el token de la invitación, define su contraseña y
    queda listo para iniciar sesión. Consume el token para que no se reutilice.
    El límite de intentos impide probar códigos de invitación en masa.
    """
    permission_classes = [AllowAny]
    throttle_scope = "crear_contrasena"

    def post(self, request):
        serializer = CrearContrasenaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        invitacion = datos["invitacion"]
        usuario = invitacion.usuario

        # Fijar la contraseña y completar datos opcionales. Con Firebase, la
        # contraseña se guarda allá (se crea su cuenta) y aquí solo el vínculo.
        if firebase.activo():
            try:
                usuario.firebase_uid = firebase.crear_o_actualizar_cuenta(
                    usuario.email, datos["password"], usuario.nombre_completo,
                )
            except Exception:
                return Response(
                    {"detail": "No se pudo crear tu cuenta de acceso en este momento. "
                               "Intenta de nuevo en unos minutos; si se repite, avisa a tu gerente."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            usuario.set_unusable_password()
        else:
            usuario.set_password(datos["password"])
        if datos.get("rut"):
            usuario.rut = datos["rut"]
        if datos.get("telefono"):
            usuario.telefono = datos["telefono"]
        usuario.save()

        # Consumir la invitación.
        invitacion.usada_en = timezone.now()
        invitacion.save(update_fields=["usada_en"])

        # Con Firebase, el frontend inicia sesión allá con la contraseña recién creada.
        if firebase.activo():
            return Response({"firebase": True, "usuario": UsuarioSerializer(usuario).data})

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
