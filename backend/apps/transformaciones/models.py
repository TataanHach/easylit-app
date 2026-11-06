"""
El corazón del sistema: la Transformación y sus piezas.

Una Transformacion recorre una máquina de estados explícita.
El MapeoCampo guarda la correspondencia origen→destino que la IA propone y el
humano aprueba. La Bitacora registra cada acción para trazabilidad: en una
licitación adjudicada, poder reconstruir de dónde salió un número seis meses
después vale más que cualquier otra cosa.

Regla de oro reflejada en el diseño: la IA solo escribe en MapeoCampo (propuesta).
El humano cambia MapeoCampo (aprobación). El worker lee MapeoCampo y escribe el
archivo final. Nadie salta pasos.
"""
import uuid

from django.db import models
from django.utils import timezone


class EstadoTransformacion(models.TextChoices):
    BORRADOR = "BORRADOR", "Borrador"                     # archivos cargados
    LIMPIEZA = "LIMPIEZA", "Limpieza aplicada"
    MAPEO_PROPUESTO = "MAPEO_PROPUESTO", "Mapeo propuesto por IA"
    EN_REVISION = "EN_REVISION", "En revisión humana"
    APROBADO = "APROBADO", "Mapeo aprobado"
    GENERADO = "GENERADO", "Documento generado"
    ERROR = "ERROR", "Error"


class Transformacion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Aislamiento: toda consulta se filtra por organización.
    organizacion = models.ForeignKey(
        "organizaciones.Organizacion",
        on_delete=models.CASCADE,
        related_name="transformaciones",
    )
    # Autoría: es lo que permite el filtro "Mías / De mi equipo / Todas".
    autor = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        related_name="transformaciones",
    )

    # Nombre que el usuario le da a la transformación para reconocerla en el
    # historial. Opcional: si queda vacío se muestra el nombre del archivo.
    nombre = models.CharField(max_length=200, blank=True)

    # --- Origen ---
    archivo_origen = models.FileField(upload_to="origen/%Y/%m/")
    nombre_origen = models.CharField(max_length=255)
    mandante = models.CharField(max_length=200, blank=True)

    # --- Destino ---
    plantilla = models.ForeignKey(
        "plantillas.Plantilla",
        on_delete=models.PROTECT,
        related_name="transformaciones",
    )
    # Archivo resultante, disponible solo cuando estado == GENERADO.
    archivo_generado = models.FileField(
        upload_to="generado/%Y/%m/", null=True, blank=True
    )

    estado = models.CharField(
        max_length=20,
        choices=EstadoTransformacion.choices,
        default=EstadoTransformacion.BORRADOR,
    )
    # Cuando estado == ERROR, aquí va la causa legible (no un stacktrace).
    detalle_error = models.CharField(max_length=500, blank=True)

    # Confianza global del mapeo (promedio ponderado), 0–100. Solo para mostrar.
    confianza = models.PositiveSmallIntegerField(null=True, blank=True)

    # Operaciones de limpieza que el usuario dejó activas (duplicados, unidades…).
    opciones_limpieza = models.JSONField(default=dict, blank=True)
    # Resumen de lo que la limpieza hizo, para mostrar cifras reales al usuario.
    resultado_limpieza = models.JSONField(default=dict, blank=True)

    creada = models.DateTimeField(default=timezone.now)
    # Cuándo terminó el procesamiento (quedó lista para revisar el mapeo). Con
    # `creada` da el tiempo que tardó, desde que se subió el archivo.
    procesada_en = models.DateTimeField(null=True, blank=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transformacion"
        ordering = ["-creada"]
        indexes = [
            models.Index(fields=["organizacion", "-creada"]),
            models.Index(fields=["autor", "-creada"]),
            models.Index(fields=["estado"]),
        ]

    def __str__(self):
        return f"{self.nombre_origen} → {self.plantilla.nombre} [{self.estado}]"

    @property
    def descargable(self):
        return self.estado == EstadoTransformacion.GENERADO and bool(self.archivo_generado)

    @property
    def duracion_proceso(self):
        """Segundos desde que se subió el archivo hasta que quedó listo el mapeo (None si no terminó)."""
        if not self.procesada_en:
            return None
        return max(0, round((self.procesada_en - self.creada).total_seconds()))


class MapeoCampo(models.Model):
    """
    Correspondencia entre una columna del origen y un campo de la plantilla.

    origen_* lo llena la IA. destino_campo lo confirma o corrige el humano. La
    confianza es la que reporta la IA. `ajustado_por_humano` distingue lo que la
    persona tocó de lo que aceptó tal cual: esa distinción es clave en la bitácora.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transformacion = models.ForeignKey(
        Transformacion, on_delete=models.CASCADE, related_name="mapeos"
    )

    # Lo que detectó la IA en el origen.
    origen_columna = models.CharField(max_length=150)      # "Monto estimado (UF)"

    # A qué campo destino va. Null = sin asignar (bloquea la generación).
    destino_campo = models.ForeignKey(
        "plantillas.CampoPlantilla",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mapeos",
    )

    confianza = models.PositiveSmallIntegerField(default=0)  # 0–100
    # Motivo de la IA cuando la confianza es baja, para mostrar en el tooltip:
    # "UF en origen, CLP en destino; sin tasa definida".
    motivo = models.CharField(max_length=300, blank=True)

    ajustado_por_humano = models.BooleanField(default=False)

    class Meta:
        db_table = "mapeo_campo"
        ordering = ["-confianza"]

    def __str__(self):
        destino = self.destino_campo.nombre if self.destino_campo else "— sin asignar —"
        return f"{self.origen_columna} → {destino} ({self.confianza}%)"


class Bitacora(models.Model):
    """
    Registro append-only de auditoría. Nunca se edita ni se borra.

    Cada evento relevante deja huella: quién subió, qué limpió, qué propuso la
    IA, qué cambió el humano, quién aprobó, cuándo se generó. Esta tabla ES la
    trazabilidad del sistema.
    """

    class Evento(models.TextChoices):
        CARGA = "CARGA", "Archivos cargados"
        LIMPIEZA = "LIMPIEZA", "Limpieza ejecutada"
        MAPEO_IA = "MAPEO_IA", "Mapeo propuesto por IA"
        AJUSTE_HUMANO = "AJUSTE_HUMANO", "Ajuste humano del mapeo"
        TASA_CONFIRMADA = "TASA_CONFIRMADA", "Tasa de conversión confirmada"
        APROBACION = "APROBACION", "Mapeo aprobado"
        GENERACION = "GENERACION", "Documento generado"
        ERROR = "ERROR", "Error registrado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transformacion = models.ForeignKey(
        Transformacion, on_delete=models.CASCADE, related_name="bitacora"
    )
    evento = models.CharField(max_length=20, choices=Evento.choices)
    # Quién lo hizo. Null si fue el sistema/worker (ej. la propuesta de IA).
    autor = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        related_name="eventos_bitacora",
    )
    # Detalle estructurado: qué campo cambió, valor antes/después, modelo de IA
    # usado, cifras de la limpieza, etc.
    detalle = models.JSONField(default=dict, blank=True)
    creado = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "bitacora"
        ordering = ["creado"]  # orden cronológico para el timeline
        indexes = [models.Index(fields=["transformacion", "creado"])]

    def __str__(self):
        return f"{self.get_evento_display()} · {self.creado:%Y-%m-%d %H:%M}"
