"""
Organización: la raíz del aislamiento de datos.

Modelo de negocio B (una sola organización por ahora), pero todo cuelga de aquí
desde el día uno. Cuando migremos a A (multiempresa SaaS), el aislamiento ya
está hecho: basta filtrar cada consulta por la organización del usuario. Meter
esto después significaría reescribir todos los querysets, así que va ahora.
"""
import uuid

from django.db import models
from django.utils import timezone


class Organizacion(models.Model):
    """Una empresa constructora que usa la plataforma."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    nombre = models.CharField(max_length=200)
    # RUT de la empresa (persona jurídica). Guardamos normalizado sin puntos ni
    # guion; el dígito verificador se valida en el serializer, no aquí.
    rut = models.CharField(max_length=12, unique=True)
    giro = models.CharField(max_length=200, blank=True)

    # Contacto principal (normalmente el gerente).
    email_contacto = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    comuna = models.CharField(max_length=100, blank=True)

    # Permite suspender el acceso de toda una organización sin borrar sus datos.
    activa = models.BooleanField(default=True)

    # Preferencias que afectan el procesamiento, con valores por defecto seguros.
    # anonimizar_montos ON por defecto: en el tier gratuito de Gemini los prompts
    # se usan para entrenar, así que por defecto los montos NO salen de la empresa.
    anonimizar_montos = models.BooleanField(default=True)

    creada = models.DateTimeField(default=timezone.now)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organizacion"
        verbose_name = "organización"
        verbose_name_plural = "organizaciones"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
