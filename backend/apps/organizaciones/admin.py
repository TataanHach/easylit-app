from django.contrib import admin

from .models import Organizacion


@admin.register(Organizacion)
class OrganizacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "rut", "activa", "anonimizar_montos", "creada")
    list_filter = ("activa", "anonimizar_montos")
    search_fields = ("nombre", "rut")
    readonly_fields = ("id", "creada", "actualizada")
