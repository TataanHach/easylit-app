"""
Serializers de plantillas.

La plantilla es el formato destino de un mandante. El campo `campos` se anida
para que el frontend reciba la plantilla y su lista de campos en una sola
llamada, que es lo que necesita el editor de mapeo.
"""
from rest_framework import serializers

from apps.plantillas.models import CampoPlantilla, Plantilla, UnidadCanonica


class CampoPlantillaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampoPlantilla
        fields = (
            "id", "plantilla", "nombre", "columna_excel", "orden",
            "tipo", "obligatorio", "moneda_destino", "descripcion",
            "celda_destino", "etiqueta_busqueda", "hoja_destino",
        )
        read_only_fields = ("id",)

    def validate_plantilla(self, plantilla):
        # El campo debe pertenecer a una plantilla de la organización del usuario.
        request = self.context.get("request")
        if request and plantilla.organizacion_id != request.user.organizacion_id:
            raise serializers.ValidationError("Esa plantilla no es de tu organización.")
        return plantilla


class PlantillaSerializer(serializers.ModelSerializer):
    """Lista y detalle de plantilla. Los campos se incluyen anidados."""

    campos = CampoPlantillaSerializer(many=True, read_only=True)
    total_campos = serializers.IntegerField(read_only=True)

    class Meta:
        model = Plantilla
        fields = (
            "id", "nombre", "mandante", "sector", "formato",
            "archivo", "hoja_datos", "fila_encabezado", "fila_primer_dato",
            "favorita", "archivada", "usos", "total_campos", "campos",
            "creada",
        )
        read_only_fields = ("id", "usos", "creada")


class PlantillaListaSerializer(serializers.ModelSerializer):
    """Versión ligera para la galería: sin los campos anidados."""

    total_campos = serializers.IntegerField(read_only=True)

    class Meta:
        model = Plantilla
        fields = (
            "id", "nombre", "mandante", "sector", "formato",
            "favorita", "usos", "total_campos", "creada",
        )


class UnidadCanonicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnidadCanonica
        fields = ("id", "simbolo", "nombre", "alias")