"""
Serializers de plantillas.

La plantilla es el formato destino de un mandante. El campo `campos` se anida
para que el frontend reciba la plantilla y su lista de campos en una sola
llamada, que es lo que necesita el editor de mapeo.
"""
from rest_framework import serializers

from apps.common.archivos import validar_tamano
from apps.plantillas.models import CampoPlantilla, Plantilla, UnidadCanonica


class CampoPlantillaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampoPlantilla
        fields = (
            "id", "plantilla", "nombre", "columna_excel", "orden",
            "tipo", "obligatorio", "moneda_destino", "descripcion",
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
            "archivo", "hoja_datos", "fila_encabezado", "fila_primer_dato",
            "favorita", "archivada", "usos", "total_campos", "campos",
            "creada",
        )
        read_only_fields = ("id", "usos", "creada")

    EXTENSIONES = (".xlsx", ".xlsm", ".xls", ".csv")

    def validate_archivo(self, archivo):
        if not archivo.name.lower().endswith(self.EXTENSIONES):
            raise serializers.ValidationError(
                f"El archivo «{archivo.name}» no es un Excel ni un CSV. Sube el formato "
                "del mandante como .xlsx, .xls o .csv."
            )
        if archivo.size == 0:
            raise serializers.ValidationError(
                f"El archivo «{archivo.name}» está vacío. Revisa que se haya guardado "
                "bien y vuelve a subirlo."
            )
        validar_tamano(archivo)
        return archivo


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