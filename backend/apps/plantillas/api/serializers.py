"""
Serializers de plantillas.

La plantilla es el formato destino de un mandante. El campo `campos` se anida
para que el frontend reciba la plantilla y su lista de campos en una sola
llamada, que es lo que necesita el editor de mapeo.
"""
from rest_framework import serializers

from apps.common.archivos import validar_planilla
from apps.common.textos import normalizar_mandante, problema_caracteres
from apps.plantillas.models import CampoPlantilla, Plantilla


def _sin_caracteres_raros(valor):
    """Rechaza símbolos como " # $ @ en los textos de la plantilla."""
    problema = problema_caracteres(valor)
    if problema:
        raise serializers.ValidationError(problema)
    return valor


class CampoPlantillaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampoPlantilla
        fields = (
            "id", "plantilla", "nombre", "orden",
            "tipo", "obligatorio", "moneda_destino",
            "celda_destino", "etiqueta_busqueda", "hoja_destino",
            "formato_numero",
        )
        read_only_fields = ("id",)
        # La unicidad (plantilla, nombre) se revisa en validate() con un mensaje
        # claro; el validador automático de DRF dice "deben formar un conjunto único".
        validators = []

    def validate_plantilla(self, plantilla):
        # El campo debe pertenecer a una plantilla de la organización del usuario.
        request = self.context.get("request")
        if request and plantilla.organizacion_id != request.user.organizacion_id:
            raise serializers.ValidationError("Esa plantilla no es de tu organización.")
        return plantilla

    def validate(self, attrs):
        plantilla = attrs.get("plantilla") or getattr(self.instance, "plantilla", None)
        nombre = attrs.get("nombre", getattr(self.instance, "nombre", None))
        if plantilla and nombre:
            repetido = CampoPlantilla.objects.filter(plantilla=plantilla, nombre__iexact=nombre)
            if self.instance:
                repetido = repetido.exclude(pk=self.instance.pk)
            if repetido.exists():
                raise serializers.ValidationError({
                    "nombre": f"Ya hay un campo llamado «{nombre}» en esta plantilla. "
                              "Usa otro nombre para poder distinguirlos."
                })
        return attrs


class PlantillaSerializer(serializers.ModelSerializer):
    """Lista y detalle de plantilla. Los campos se incluyen anidados."""

    campos = CampoPlantillaSerializer(many=True, read_only=True)
    total_campos = serializers.IntegerField(read_only=True)

    class Meta:
        model = Plantilla
        fields = (
            "id", "nombre", "mandante", "sector", "formato",
            "archivo", "favorita", "archivada", "total_campos", "campos",
            "creada",
        )
        read_only_fields = ("id", "creada")

    def validate_archivo(self, archivo):
        return validar_planilla(archivo)

    def validate_nombre(self, nombre):
        return _sin_caracteres_raros(nombre)

    def validate_sector(self, sector):
        return _sin_caracteres_raros(sector)

    def validate_mandante(self, mandante):
        # Toda plantilla pertenece a un mandante: es lo que agrupa y filtra las plantillas.
        mandante = normalizar_mandante(mandante)
        if not mandante:
            raise serializers.ValidationError(
                "Falta el mandante. Escribe para quién es este formato (ej. MINEDUC, Codelco)."
            )
        return _sin_caracteres_raros(mandante)

    def validate(self, attrs):
        # Al crear, el mandante es obligatorio aunque no se haya enviado el campo.
        if self.instance is None and not attrs.get("mandante"):
            raise serializers.ValidationError({
                "mandante": "Falta el mandante. Escribe para quién es este formato (ej. MINEDUC, Codelco)."
            })
        return attrs


class PlantillaListaSerializer(serializers.ModelSerializer):
    """Versión ligera para la galería: sin los campos anidados."""

    total_campos = serializers.IntegerField(read_only=True)

    class Meta:
        model = Plantilla
        fields = (
            "id", "nombre", "mandante", "sector", "formato",
            "favorita", "total_campos", "creada",
        )
