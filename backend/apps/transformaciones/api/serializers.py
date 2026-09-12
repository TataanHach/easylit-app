"""
Serializers de transformaciones.

Separo la vista de LISTA (ligera, para la tabla del historial) de la de DETALLE
(completa, con partidas, mapeos y bitácora). La lista añade el nombre del autor
y de la plantilla para que la tabla no tenga que resolver esas referencias.
"""
from rest_framework import serializers

from apps.transformaciones.models import (
    Bitacora,
    MapeoCampo,
    Partida,
    Transformacion,
)


class TransformacionListaSerializer(serializers.ModelSerializer):
    """Fila de la tabla del historial."""

    autor_nombre = serializers.CharField(source="autor.nombre_completo", read_only=True)
    plantilla_nombre = serializers.CharField(source="plantilla.nombre", read_only=True)
    descargable = serializers.BooleanField(read_only=True)

    class Meta:
        model = Transformacion
        fields = (
            "id", "nombre_origen", "mandante",
            "plantilla", "plantilla_nombre",
            "autor", "autor_nombre",
            "estado", "confianza", "descargable", "creada",
        )


class CrearTransformacionSerializer(serializers.ModelSerializer):
    """
    Alta de una transformación: subir el Excel origen y elegir la plantilla
    destino. El autor y la organización se asignan en la vista, no se aceptan
    como entrada (seguridad: nadie crea transformaciones a nombre de otro).
    """

    class Meta:
        model = Transformacion
        fields = ("id", "archivo_origen", "nombre_origen", "mandante", "plantilla")
        read_only_fields = ("id",)

    def validate_plantilla(self, plantilla):
        # La plantilla debe pertenecer a la organización del usuario.
        request = self.context["request"]
        if plantilla.organizacion_id != request.user.organizacion_id:
            raise serializers.ValidationError("Esa plantilla no pertenece a tu organización.")
        return plantilla


class MapeoCampoSerializer(serializers.ModelSerializer):
    destino_nombre = serializers.CharField(
        source="destino_campo.nombre", read_only=True, default=None
    )

    class Meta:
        model = MapeoCampo
        fields = (
            "id", "origen_columna", "origen_muestra",
            "destino_campo", "destino_nombre",
            "confianza", "motivo", "ajustado_por_humano",
        )


class PartidaSerializer(serializers.ModelSerializer):
    total_calculado = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True
    )

    class Meta:
        model = Partida
        fields = (
            "id", "codigo", "capitulo", "es_capitulo", "descripcion",
            "unidad_origen", "unidad_canonica",
            "cantidad", "precio_unitario", "total", "total_calculado",
            "orden", "requiere_revision",
        )


class BitacoraSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.CharField(
        source="autor.nombre_completo", read_only=True, default="Sistema"
    )
    evento_display = serializers.CharField(source="get_evento_display", read_only=True)

    class Meta:
        model = Bitacora
        fields = ("id", "evento", "evento_display", "autor_nombre", "detalle", "creado")


class TransformacionDetalleSerializer(serializers.ModelSerializer):
    """Detalle completo: incluye mapeos, partidas y bitácora anidados."""

    autor_nombre = serializers.CharField(source="autor.nombre_completo", read_only=True)
    plantilla_nombre = serializers.CharField(source="plantilla.nombre", read_only=True)
    descargable = serializers.BooleanField(read_only=True)
    mapeos = MapeoCampoSerializer(many=True, read_only=True)
    bitacora = BitacoraSerializer(many=True, read_only=True)

    class Meta:
        model = Transformacion
        fields = (
            "id", "nombre_origen", "mandante",
            "plantilla", "plantilla_nombre",
            "autor", "autor_nombre",
            "estado", "confianza", "detalle_error",
            "opciones_limpieza", "resultado_limpieza", "tasa_uf_clp",
            "descargable", "creada", "actualizada",
            "mapeos", "bitacora",
        )
