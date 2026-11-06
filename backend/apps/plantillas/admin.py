from django.contrib import admin

from .models import CampoPlantilla, Plantilla


class CampoPlantillaInline(admin.TabularInline):
    """Permite editar los campos de la plantilla en la misma página."""
    model = CampoPlantilla
    extra = 1
    fields = ("orden", "nombre", "tipo", "obligatorio", "moneda_destino", "celda_destino", "hoja_destino")


@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "mandante", "sector", "formato", "total_campos", "favorita")
    list_filter = ("formato", "sector", "favorita", "archivada")
    search_fields = ("nombre", "mandante")
    readonly_fields = ("id", "creada", "actualizada")
    inlines = [CampoPlantillaInline]

