"""
Permisos por rol, reutilizables en toda la API.

Centralizar aquí evita repetir comprobaciones de rol en cada vista y hace que la
regla sea una sola, fácil de auditar.
"""
from rest_framework.permissions import BasePermission


class EsGerenteOSuperadmin(BasePermission):
    """Solo gerentes y superadmin pueden gestionar usuarios del equipo."""

    message = "Necesitas rol de gerente o superadministrador."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.puede_gestionar_usuarios
        )
