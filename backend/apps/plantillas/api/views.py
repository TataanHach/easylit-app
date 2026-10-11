"""
Vistas de plantillas.

Mismo aislamiento por organización que las transformaciones. La galería usa el
serializer ligero; el detalle trae los campos anidados para el editor de mapeo.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.plantillas.models import Plantilla, UnidadCanonica

from .serializers import (
    PlantillaListaSerializer,
    PlantillaSerializer,
    UnidadCanonicaSerializer,
)


class PlantillaViewSet(viewsets.ModelViewSet):
    """
    GET    /api/plantillas/            galería (ligera)
    POST   /api/plantillas/            crear
    GET    /api/plantillas/{id}/       detalle con campos
    GET    /api/plantillas/{id}/hojas/ hojas del Excel de la plantilla
    """

    def get_queryset(self):
        usuario = self.request.user
        if usuario.es_superadmin:
            qs = Plantilla.objects.all()
        else:
            qs = Plantilla.objects.filter(organizacion=usuario.organizacion)

        # No mostrar archivadas salvo que se pidan explícitamente.
        if self.request.query_params.get("archivadas") != "true":
            qs = qs.filter(archivada=False)

        return qs.prefetch_related("campos")

    def get_serializer_class(self):
        if self.action == "list":
            return PlantillaListaSerializer
        return PlantillaSerializer

    def perform_create(self, serializer):
        serializer.save(
            organizacion=self.request.user.organizacion,
            creada_por=self.request.user,
        )

    def destroy(self, request, *args, **kwargs):
        # Una plantilla usada por transformaciones está protegida (PROTECT): se
        # explica el motivo en vez de devolver un error 500.
        plantilla = self.get_object()
        usos = plantilla.transformaciones.count()
        if usos:
            return Response(
                {"detail": f"La plantilla «{plantilla.nombre}» la usan {usos} "
                           f"transformación(es) del historial, y borrarla dejaría esos "
                           f"documentos sin formato. Elimina primero esas transformaciones "
                           f"o deja la plantilla como está."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def hojas(self, request, pk=None):
        """
        Hojas del Excel de la plantilla y una revisión para el editor de campos:
          hojas:     ["Identificación", "Experiencia", "Oferta"]
          detalle:   por hoja, si es "tabla" (se llena sola con la tabla del
                     origen; trae sus columnas) o "formulario" (necesita campos).
          problemas: {campo_id: motivo} de los campos que no se podrán escribir
                     (etiqueta que no está en la hoja, campo dentro de una tabla…).

        Si el archivo no es un Excel legible, devuelve listas vacías (no rompe: el
        editor simplemente no mostrará hojas y el campo irá a la hoja activa).
        """
        from apps.transformaciones.services.generacion import revisar_plantilla

        plantilla = self.get_object()
        error = ""
        try:
            revision = revisar_plantilla(plantilla.archivo.path, list(plantilla.campos.all()))
        except FileNotFoundError:
            revision, error = None, (
                "No se encontró el archivo Excel de la plantilla en el servidor. Vuelve a "
                "crear la plantilla subiendo el archivo de nuevo."
            )
        except Exception:
            revision, error = None, (
                "El archivo de la plantilla no se pudo leer como Excel (.xlsx). Puede estar "
                "dañado, protegido con contraseña o ser de otro formato. Ábrelo en Excel, "
                "guárdalo como .xlsx y vuelve a crear la plantilla."
            )
        revision = revision or {"hojas": [], "problemas": {}, "ubicaciones": {}}
        return Response({
            "hojas": [h["nombre"] for h in revision["hojas"]],
            "detalle": revision["hojas"],
            "problemas": revision["problemas"],
            "ubicaciones": revision["ubicaciones"],
            "error": error,
        })


class UnidadCanonicaViewSet(viewsets.ModelViewSet):
    """Catálogo de unidades canónicas de la organización."""
    serializer_class = UnidadCanonicaSerializer

    def get_queryset(self):
        usuario = self.request.user
        if usuario.es_superadmin:
            return UnidadCanonica.objects.all()
        return UnidadCanonica.objects.filter(organizacion=usuario.organizacion)

    def perform_create(self, serializer):
        serializer.save(organizacion=self.request.user.organizacion)


class CampoPlantillaViewSet(viewsets.ModelViewSet):
    """
    CRUD de campos de una plantilla.
      GET/POST   /api/campos/           listar (filtrado por ?plantilla=id) / crear
      PATCH/DELETE /api/campos/{id}/    editar / borrar
    """
    from apps.plantillas.api.serializers import CampoPlantillaSerializer
    serializer_class = CampoPlantillaSerializer

    def get_queryset(self):
        from apps.plantillas.models import CampoPlantilla
        usuario = self.request.user
        if usuario.es_superadmin:
            qs = CampoPlantilla.objects.all()
        else:
            qs = CampoPlantilla.objects.filter(plantilla__organizacion=usuario.organizacion)
        plantilla_id = self.request.query_params.get("plantilla")
        if plantilla_id:
            qs = qs.filter(plantilla_id=plantilla_id)
        return qs.select_related("plantilla")