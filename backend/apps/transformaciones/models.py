"""
El corazón del sistema: la Transformación y sus piezas.

Una Transformacion recorre una máquina de estados explícita. Cada partida del
itemizado origen se guarda como fila (Partida) para poder reconciliar totales.
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

    # Tasa UF→CLP confirmada por el humano, si la conversión aplica. Se guarda
    # para que quede registrada junto al documento (auditoría).
    tasa_uf_clp = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    creada = models.DateTimeField(default=timezone.now)
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
    origen_muestra = models.JSONField(default=list, blank=True)  # pocas celdas de ejemplo

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


class Partida(models.Model):
    """
    Una fila del itemizado origen, ya limpia.

    Guardarlas permite reconciliar totales (cantidad×precio, subtotales por
    capítulo, total contra el documento original) antes de dejar generar. Es la
    base de la validación aritmética determinista que corre el worker.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transformacion = models.ForeignKey(
        Transformacion, on_delete=models.CASCADE, related_name="partidas"
    )

    # Jerarquía del itemizado: "2", "2.1", "2.1.3".
    codigo = models.CharField(max_length=30, blank=True)
    capitulo = models.CharField(max_length=30, blank=True)  # capítulo al que pertenece
    es_capitulo = models.BooleanField(default=False)        # fila de subtotal/título

    descripcion = models.TextField(blank=True)

    # Unidad tal como vino y su forma canónica resuelta. Si canonica queda vacía
    # en una partida no-capítulo, la validación de unidades falla.
    unidad_origen = models.CharField(max_length=30, blank=True)
    unidad_canonica = models.ForeignKey(
        "plantillas.UnidadCanonica",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="partidas",
    )

    cantidad = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    precio_unitario = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    orden = models.PositiveIntegerField(default=0)
    # True si la fila necesita atención humana (baja confianza o sin unidad).
    requiere_revision = models.BooleanField(default=False)

    class Meta:
        db_table = "partida"
        ordering = ["orden"]
        indexes = [models.Index(fields=["transformacion", "orden"])]

    def __str__(self):
        return f"{self.codigo} · {self.descripcion[:40]}"

    @property
    def total_calculado(self):
        """cantidad × precio, para comparar contra `total` en la validación."""
        if self.cantidad is None or self.precio_unitario is None:
            return None
        return self.cantidad * self.precio_unitario


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
