from django.contrib import admin

from .models import CampoPlantilla, Plantilla, UnidadCanonica


class CampoPlantillaInline(admin.TabularInline):
    """Permite editar los campos de la plantilla en la misma página."""
    model = CampoPlantilla
    extra = 1
    fields = ("orden", "nombre", "columna_excel", "tipo", "obligatorio", "moneda_destino")


@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "mandante", "sector", "formato", "total_campos", "usos", "favorita")
    list_filter = ("formato", "sector", "favorita", "archivada")
    search_fields = ("nombre", "mandante")
    readonly_fields = ("id", "creada", "actualizada", "usos")
    inlines = [CampoPlantillaInline]


@admin.register(UnidadCanonica)
class UnidadCanonicaAdmin(admin.ModelAdmin):
    list_display = ("simbolo", "nombre", "organizacion")
    list_filter = ("organizacion",)
    search_fields = ("simbolo", "nombre")
