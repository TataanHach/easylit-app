"""
Panel de administración de usuarios (/admin/), para el superadministrador.

Un usuario de EasyLit entra a la app con un código de invitación (crea su
contraseña en «Crea tu contraseña»; en producción se le crea su cuenta de
Firebase). Por eso el panel puede crear usuarios «con código de invitación»:
no se les pone contraseña y el panel muestra su código una sola vez. La acción
«Generar código de invitación» da uno nuevo a quien lo perdió o no lo tenía.
"""
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.common.textos import problema_caracteres, problema_correo

from .models import Invitacion, Rol, Usuario
from .validadores import normalizar_rut


class UsuarioCreationForm(AdminUserCreationForm):
    usable_password = forms.ChoiceField(
        label="Cómo entrará",
        required=False,
        initial="false",
        choices={
            "false": "Con código de invitación (recomendado)",
            "true": "Con contraseña",
        },
        widget=forms.RadioSelect(attrs={"class": "radiolist inline"}),
        help_text=(
            "Con código de invitación: al guardar se muestra un código que la persona usa en «Crea tu "
            "contraseña» de EasyLit. Con contraseña: solo para un superadministrador, que entra a este "
            "panel (para entrar a la app en producción necesita además vincular_firebase)."
        ),
    )

    class Meta:
        model = Usuario
        fields = ("email", "nombre_completo", "rut", "rol", "organizacion")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        problema = problema_correo(email)
        if problema:
            raise ValidationError(problema)
        return email

    def clean_nombre_completo(self):
        nombre = " ".join((self.cleaned_data.get("nombre_completo") or "").split())
        problema = problema_caracteres(nombre, persona=True)
        if problema:
            raise ValidationError(problema)
        return nombre

    def clean_rut(self):
        rut = self.cleaned_data.get("rut") or ""
        if not rut:
            return rut
        rut = normalizar_rut(rut)   # ValidationError con el motivo si el dígito no calza
        if Usuario.objects.filter(rut=rut).exists():
            raise ValidationError("Ya existe un usuario con este RUT.")
        return rut

    def clean(self):
        datos = super().clean()
        rol = datos.get("rol")
        if rol and rol != Rol.SUPERADMIN and not datos.get("organizacion"):
            self.add_error("organizacion", "Un gerente o un trabajador debe pertenecer a una organización.")
        if rol == Rol.SUPERADMIN and not datos.get("set_usable_password", True):
            self.add_error("usable_password",
                           "El superadministrador entra a este panel con contraseña: elige «Con contraseña».")
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if usuario.rol == Rol.SUPERADMIN:   # igual que createsuperuser
            usuario.is_staff = usuario.is_superuser = True
        if commit:
            usuario.save()
        return usuario


class UsuarioChangeForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = "__all__"


def _mostrar_codigo(request, usuario, invitacion):
    """Deja en pantalla el código, esa única vez (en la base solo queda su huella)."""
    vence = timezone.localtime(invitacion.expira).strftime("%d-%m-%Y")
    frontend = getattr(settings, "FRONTEND_URL", "") or ""
    donde = f"{frontend}/crear-contrasena" if frontend else "la pantalla «Crea tu contraseña» de EasyLit"
    messages.warning(
        request,
        f"Código de invitación de {usuario.nombre_completo} ({usuario.email}): {invitacion.codigo} "
        f"· vence el {vence}. Cópialo ahora: no se vuelve a mostrar. Envíaselo a la persona: entra a "
        f"{donde}, escribe su correo y el código, y crea su contraseña.",
    )


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
    actions = ["generar_codigo"]

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
            "fields": ("email", "nombre_completo", "rut", "rol", "organizacion",
                       "usable_password", "password1", "password2"),
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Creado «con código de invitación»: se genera y se muestra de inmediato.
        if not change and not obj.has_usable_password() and obj.rol != Rol.SUPERADMIN:
            _mostrar_codigo(request, obj, Invitacion.nueva(obj, request.user))

    @admin.action(description="Generar código de invitación")
    def generar_codigo(self, request, queryset):
        """Código nuevo para cada persona elegida que todavía no tiene acceso (anula el anterior)."""
        omitidos = []
        for usuario in queryset:
            if usuario.es_superadmin or not usuario.is_active or not usuario.necesita_crear_contrasena:
                omitidos.append(usuario.nombre_completo)
                continue
            _mostrar_codigo(request, usuario, Invitacion.nueva(usuario, request.user))
        if omitidos:
            messages.info(
                request,
                "Sin código nuevo (ya tienen acceso, están desactivados o son superadministradores): "
                + ", ".join(omitidos) + ".",
            )


@admin.register(Invitacion)
class InvitacionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "invitado_por", "creada", "expira", "usada_en", "vigente")
    list_filter = ("creada", "expira")
    search_fields = ("usuario__email",)
    readonly_fields = ("id", "usuario", "codigo_hash", "invitado_por", "creada", "expira", "usada_en")

    def has_add_permission(self, request):
        # Un código se crea desde Usuarios (al crearlo o con la acción «Generar código
        # de invitación»): aquí no se podría ver, porque solo se guarda su huella.
        return False
