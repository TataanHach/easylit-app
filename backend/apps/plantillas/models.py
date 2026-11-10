"""
Plantillas: los formatos destino de cada mandante.

Una Plantilla es el formato exigido por un mandante (ej. "Formato Codelco 2024").
Guarda el archivo Excel original para poder escribir DENTRO de él preservando
fórmulas y estilos, y una definición estructurada de sus campos para que la IA
sepa a qué debe mapear.
"""
import uuid

from django.db import models
from django.utils import timezone


class Plantilla(models.Model):
    """Formato destino de un mandante."""

    class Formato(models.TextChoices):
        XLSX = "XLSX", "Excel"
        CSV = "CSV", "CSV"
        PDF = "PDF", "PDF"
        DOCX = "DOCX", "Word"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.CASCADE,
        related_name="plantillas",
    )

    nombre = models.CharField(max_length=200)
    mandante = models.CharField(max_length=200, blank=True)
    # Hojas que el usuario marcó a mano: {"Hoja": "TABLA" | "FORMULARIO"}. Las que
    # no están aquí se detectan solas (palabras típicas del encabezado).
    tipos_hoja = models.JSONField(default=dict, blank=True)
    sector = models.CharField(max_length=100, blank=True)
    formato = models.CharField(max_length=8, choices=Formato.choices, default=Formato.XLSX)

    archivo = models.FileField(upload_to="plantillas/%Y/%m/")

    favorita = models.BooleanField(default=False)
    archivada = models.BooleanField(default=False)

    # Quién creó la plantilla.
    usuario = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        related_name="plantillas_creadas",
    )
    creada = models.DateTimeField(default=timezone.now)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plantilla"
        ordering = ["-favorita", "nombre"]

    def __str__(self):
        return self.nombre

    @property
    def total_campos(self):
        return self.campos.count()


class CampoPlantilla(models.Model):
    """
    Un campo/columna que la plantilla destino espera recibir.

    Esta definición es lo que se le entrega a la IA como "esquema destino" para
    que proponga el mapeo. Cuanto más rica sea (tipo, unidad esperada, si es
    obligatorio), mejor la propuesta y más estricta la validación.
    """

    class Tipo(models.TextChoices):
        TEXTO = "TEXTO", "Texto"
        NUMERO = "NUMERO", "Número"
        MONEDA = "MONEDA", "Moneda"
        FECHA = "FECHA", "Fecha"
        UNIDAD = "UNIDAD", "Unidad de medida"

    class Formato(models.TextChoices):
        """
        Cómo se muestra el valor en la celda del Excel generado. Controla el
        'number_format' de openpyxl, así el número queda como número real (no
        texto) con su símbolo. NINGUNO deja el valor tal cual.
        """
        NINGUNO = "NINGUNO", "Sin formato (tal cual)"
        ENTERO = "ENTERO", "Número entero (1.234)"
        DECIMAL = "DECIMAL", "Decimal (1.234,56)"
        PESOS = "PESOS", "Pesos chilenos ($ 1.234)"
        PESOS_DEC = "PESOS_DEC", "Pesos con decimales ($ 1.234,56)"
        PORCENTAJE = "PORCENTAJE", "Porcentaje (12,5%)"
        UF = "UF", "UF (1.234,56 UF)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plantilla = models.ForeignKey(
        Plantilla, on_delete=models.CASCADE, related_name="campos"
    )

    nombre = models.CharField(max_length=150)
    orden = models.PositiveIntegerField(default=0)

    celda_destino = models.CharField(max_length=10, blank=True)
    etiqueta_busqueda = models.CharField(max_length=150, blank=True)
    hoja_destino = models.CharField(max_length=100, blank=True)

    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.TEXTO)
    obligatorio = models.BooleanField(default=False)

    # NUEVO: cómo se formatea el número al escribirlo en la celda del Excel.
    # Solo aplica a valores numéricos; para TEXTO/FECHA se ignora.
    formato_numero = models.CharField(
        max_length=12, choices=Formato.choices, default=Formato.NINGUNO, blank=True
    )

    moneda_destino = models.CharField(max_length=10, blank=True)

    class Meta:
        db_table = "campo_plantilla"
        ordering = ["orden", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["plantilla", "nombre"],
                name="campo_unico_por_plantilla",
            )
        ]

    def __str__(self):
        return f"{self.plantilla.nombre} · {self.nombre}"