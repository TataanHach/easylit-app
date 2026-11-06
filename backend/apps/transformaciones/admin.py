from django.contrib import admin

from .models import Bitacora, MapeoCampo, Transformacion


class MapeoCampoInline(admin.TabularInline):
    model = MapeoCampo
    extra = 0
    readonly_fields = ("origen_columna", "confianza")


class BitacoraInline(admin.TabularInline):
    model = Bitacora
    extra = 0
    readonly_fields = ("evento", "autor", "detalle", "creado")
    can_delete = False


@admin.register(Transformacion)
class TransformacionAdmin(admin.ModelAdmin):
    list_display = ("nombre_origen", "plantilla", "autor", "estado", "confianza", "creada")
    list_filter = ("estado", "organizacion", "creada")
    search_fields = ("nombre_origen", "mandante")
    readonly_fields = ("id", "creada", "actualizada")
    inlines = [MapeoCampoInline, BitacoraInline]


@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ("transformacion", "evento", "autor", "creado")
    list_filter = ("evento", "creado")
    readonly_fields = ("id", "creado")
