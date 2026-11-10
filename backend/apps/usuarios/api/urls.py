"""Rutas de autenticación, montadas bajo /api/auth/."""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CrearContrasenaView,
    EquipoView,
    EstadoCorreoView,
    InvitarUsuarioView,
    LoginView,
    LogoutView,
    NuevaInvitacionView,
    PerfilView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("estado-correo/", EstadoCorreoView.as_view(), name="estado_correo"),
    path("invitar/", InvitarUsuarioView.as_view(), name="invitar"),
    path("equipo/", EquipoView.as_view(), name="equipo"),
    path("equipo/<uuid:pk>/invitacion/", NuevaInvitacionView.as_view(), name="nueva_invitacion"),
    path("crear-contrasena/", CrearContrasenaView.as_view(), name="crear_contrasena"),
    path("perfil/", PerfilView.as_view(), name="perfil"),
]
