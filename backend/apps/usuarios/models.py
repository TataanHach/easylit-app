"""
Usuario y su flujo de alta.

Usamos un usuario custom con login por CORREO (no username), porque así lo pediste
y porque el correo es lo que el gerente da de alta. El flujo de invitación es:

  1. El gerente crea el usuario con su correo. Queda SIN contraseña utilizable
     y con un token de invitación.
  2. El trabajador entra por primera vez, el sistema detecta que no tiene
     contraseña y le pide crearla (consume el token).
  3. A partir de ahí inicia sesión normal con correo + contraseña.

Roles:
  - SUPERADMIN: EasyLit. Ve todo el sistema. No pertenece a una organización.
  - GERENTE:    admin de su organización. Puede crear usuarios de su empresa.
  - TRABAJADOR: usa la plataforma dentro de su organización.
"""
import re
import secrets
import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.crypto import salted_hmac

# --- Código de invitación ---
# 8 caracteres de mayúsculas y números, sin los que se confunden al copiarlo o
# dictarlo (I, O, 0, 1): 32^8 ≈ 1,1 billón de combinaciones.
ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LARGO_CODIGO = 8
_SAL_CODIGO = "easylit.invitacion"


def normalizar_codigo(texto):
    """'k7m2-qx9p ' → 'K7M2QX9P': da igual si lo pegan con guion, espacios o en minúsculas."""
    return re.sub(r"[\s-]", "", texto or "").upper()


def codigo_valido(texto):
    codigo = normalizar_codigo(texto)
    return len(codigo) == LARGO_CODIGO and all(c in ALFABETO_CODIGO for c in codigo)


def huella_codigo(texto):
    """
    Lo que se guarda en la base en vez del código: un HMAC-SHA256 con la
    SECRET_KEY del servidor. No se puede volver atrás, y sin la clave tampoco se
    puede adivinar probando códigos contra una copia de la base.
    """
    return salted_hmac(_SAL_CODIGO, normalizar_codigo(texto), algorithm="sha256").hexdigest()


def formatear_codigo(codigo):
    """'K7M2QX9P' → 'K7M2-QX9P' (más fácil de leer y copiar)."""
    return f"{codigo[:4]}-{codigo[4:]}"


class Rol(models.TextChoices):
    SUPERADMIN = "SUPERADMIN", "Superadministrador"
    GERENTE = "GERENTE", "Gerente"
    TRABAJADOR = "TRABAJADOR", "Trabajador"


class UsuarioManager(BaseUserManager):
    """Manager que crea usuarios por correo en vez de por username."""

    use_in_migrations = True

    def _crear(self, email, password, **extra):
        if not email:
            raise ValueError("El correo es obligatorio")
        email = self.normalize_email(email).lower()
        usuario = self.model(email=email, **extra)
        if password:
            usuario.set_password(password)
        else:
            # Sin contraseña utilizable: el usuario la creará en el primer ingreso.
            usuario.set_unusable_password()
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra):
        extra.setdefault("rol", Rol.TRABAJADOR)
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(email, password, **extra)

    def create_superuser(self, email, password, **extra):
        extra.setdefault("rol", Rol.SUPERADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        if extra["is_staff"] is not True or extra["is_superuser"] is not True:
            raise ValueError("El superusuario necesita is_staff e is_superuser en True")
        return self._crear(email, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(unique=True)
    nombre_completo = models.CharField(max_length=200)
    # RUT de la persona, normalizado sin puntos ni guion. Opcional al momento de
    # la invitación (el gerente puede no tenerlo), obligatorio se puede exigir
    # al crear la contraseña.
    rut = models.CharField(max_length=12, blank=True)
    telefono = models.CharField(max_length=30, blank=True)

    # Cuenta de Firebase vinculada (cuando el login lo hace Firebase). Vacío =
    # aún no activa su cuenta. Es lo que une el token de Firebase con este usuario.
    firebase_uid = models.CharField(max_length=128, unique=True, null=True, blank=True)

    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.TRABAJADOR)

    # Superadmin no pertenece a ninguna organización → null. Gerente y trabajador
    # siempre pertenecen a una. PROTECT evita borrar una organización con usuarios.
    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.PROTECT,
        related_name="usuarios",
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # acceso al admin de Django

    creado = models.DateTimeField(default=timezone.now)
    actualizado = models.DateTimeField(auto_now=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombre_completo"]  # se piden al crear superusuario por consola

    class Meta:
        db_table = "usuario"
        ordering = ["nombre_completo"]
        constraints = [
            # Todo usuario que no sea superadmin DEBE tener organización.
            models.CheckConstraint(
                name="usuario_no_superadmin_requiere_org",
                condition=(
                    models.Q(rol="SUPERADMIN")
                    | models.Q(organizacion__isnull=False)
                ),
            ),
        ]

    def __str__(self):
        return f"{self.nombre_completo} <{self.email}>"

    # --- Ayudas de rol, para que las vistas no comparen strings sueltos ---
    @property
    def es_superadmin(self):
        return self.rol == Rol.SUPERADMIN

    @property
    def es_gerente(self):
        return self.rol == Rol.GERENTE

    @property
    def puede_gestionar_usuarios(self):
        """Superadmin (cualquiera) y gerente (los de su organización)."""
        return self.rol in (Rol.SUPERADMIN, Rol.GERENTE)

    @property
    def necesita_crear_contrasena(self):
        """True si fue invitado y aún no define contraseña."""
        from django.conf import settings
        if settings.FIREBASE_PROJECT_ID:
            return not self.firebase_uid   # la contraseña vive en Firebase
        return not self.has_usable_password()


class Invitacion(models.Model):
    """
    Token de un solo uso para el flujo de primer ingreso.

    Se crea cuando el gerente invita a un colaborador. El gerente le envía el
    código (8 caracteres) y, al crear su contraseña, el colaborador lo consume y
    queda inutilizable.

    El código NO se guarda: solo su huella (ver huella_codigo). Por eso el
    gerente lo ve una sola vez, al invitar o al generar uno nuevo.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name="invitaciones"
    )
    # HMAC-SHA256 del código (64 caracteres hexadecimales).
    codigo_hash = models.CharField(max_length=64, unique=True, db_index=True)

    invitado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        related_name="invitaciones_enviadas",
    )

    creada = models.DateTimeField(default=timezone.now)
    expira = models.DateTimeField()
    usada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "invitacion"
        ordering = ["-creada"]

    def __str__(self):
        estado = "usada" if self.usada_en else "pendiente"
        return f"Invitación a {self.usuario.email} ({estado})"

    @property
    def vigente(self):
        return self.usada_en is None and self.expira > timezone.now()

    @classmethod
    def nueva(cls, usuario, invitado_por):
        """
        Crea un código nuevo para `usuario` y anula los que aún servían: así solo
        vale el último que entregó el gerente (si reenvía uno, el viejo ya no entra).

        Devuelve la invitación con el atributo `codigo` (formato K7M2-QX9P) para
        mostrárselo al gerente esa única vez; en la base queda solo la huella.
        """
        from django.conf import settings

        ahora = timezone.now()
        cls.objects.filter(usuario=usuario, usada_en__isnull=True, expira__gt=ahora).update(expira=ahora)
        while True:
            codigo = "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(LARGO_CODIGO))
            huella = huella_codigo(codigo)
            if not cls.objects.filter(codigo_hash=huella).exists():   # choque: casi imposible
                break
        invitacion = cls.objects.create(
            usuario=usuario,
            codigo_hash=huella,
            invitado_por=invitado_por,
            expira=ahora + timedelta(days=settings.INVITACION_DIAS_VIGENCIA),
        )
        invitacion.codigo = formatear_codigo(codigo)
        return invitacion

    @classmethod
    def buscar(cls, codigo):
        """La invitación de ese código, o None (también si el formato no calza)."""
        if not codigo_valido(codigo):
            return None
        return cls.objects.select_related("usuario").filter(codigo_hash=huella_codigo(codigo)).first()
