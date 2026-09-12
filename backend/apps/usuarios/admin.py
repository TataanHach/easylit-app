from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Invitacion, Usuario


class UsuarioCreationForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ("email", "nombre_completo", "rol", "organizacion")


class UsuarioChangeForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = "__all__"


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    add_form = UsuarioCreationForm
    form = UsuarioChangeForm
    model = Usuario

    # Como el login es por correo (no username), hay que redefinir cómo se
    # ordena, busca y agrupa todo en el admin.
    ordering = ("nombre_completo",)
    list_display = ("email", "nombre_completo", "rol", "organizacion", "is_active")
    list_filter = ("rol", "is_active", "organizacion")
    search_fields = ("email", "nombre_completo", "rut")
    readonly_fields = ("id", "creado", "actualizado", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("nombre_completo", "rut", "telefono")}),
        ("Rol y organización", {"fields": ("rol", "organizacion")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login", "creado", "actualizado")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nombre_completo", "rol", "organizacion", "password1", "password2"),
        }),
    )


@admin.register(Invitacion)
class InvitacionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "invitado_por", "creada", "expira", "usada_en", "vigente")
    list_filter = ("creada", "expira")
    search_fields = ("usuario__email",)
    readonly_fields = ("id", "token", "creada", "usada_en")
