"""
Vistas de transformaciones.

Dos reglas de oro que se aplican en TODAS las consultas:

  1. Aislamiento por organización: un usuario solo ve datos de SU organización.
  2. Alcance por autor: el parámetro ?alcance= filtra Mías / Equipo / Todas.
"""
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.transformaciones.models import Bitacora, MapeoCampo, Transformacion

from .serializers import (
    CrearTransformacionSerializer,
    MapeoCampoSerializer,
    TransformacionDetalleSerializer,
    TransformacionListaSerializer,
)


class TransformacionViewSet(viewsets.ModelViewSet):
    """
    CRUD de transformaciones + acciones del flujo.
    """

    def get_queryset(self):
        usuario = self.request.user
        if usuario.es_superadmin:
            qs = Transformacion.objects.all()
        else:
            qs = Transformacion.objects.filter(organizacion=usuario.organizacion)

        alcance = self.request.query_params.get("alcance", "mine")
        if alcance == "mine":
            qs = qs.filter(autor=usuario)
        elif alcance == "team":
            qs = qs.exclude(autor=usuario)

        estado = self.request.query_params.get("estado")
        if estado:
            qs = qs.filter(estado=estado)

        return qs.select_related("autor", "plantilla")

    def get_serializer_class(self):
        if self.action == "create":
            return CrearTransformacionSerializer
        if self.action in ("retrieve", "aprobar"):
            return TransformacionDetalleSerializer
        return TransformacionListaSerializer

    def perform_create(self, serializer):
        usuario = self.request.user
        transformacion = serializer.save(
            autor=usuario,
            organizacion=usuario.organizacion,
        )
        Bitacora.objects.create(
            transformacion=transformacion,
            evento=Bitacora.Evento.CARGA,
            autor=usuario,
            detalle={
                "archivo": transformacion.nombre_origen,
                "plantilla": transformacion.plantilla.nombre,
            },
        )
        try:
            from apps.transformaciones.tasks import procesar_transformacion
            procesar_transformacion.delay(str(transformacion.id))
        except Exception:
            pass

    def perform_destroy(self, instance):
        usuario = self.request.user
        if instance.autor_id != usuario.id and not usuario.puede_gestionar_usuarios:
            raise PermissionDenied("No puedes borrar transformaciones de otra persona.")
        instance.delete()

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        transformacion = self.get_object()
        from apps.transformaciones.models import EstadoTransformacion
        transformacion.estado = EstadoTransformacion.APROBADO
        transformacion.save(update_fields=["estado"])
        Bitacora.objects.create(
            transformacion=transformacion,
            evento=Bitacora.Evento.APROBACION,
            autor=request.user,
            detalle={"nota": "Mapeo aprobado por el usuario."},
        )
        serializer = self.get_serializer(transformacion)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def generar(self, request, pk=None):
        from apps.transformaciones.models import EstadoTransformacion
        from apps.transformaciones.tasks import generar_documento_tarea

        transformacion = self.get_object()
        transformacion.estado = EstadoTransformacion.APROBADO
        transformacion.save(update_fields=["estado"])
        generar_documento_tarea(str(transformacion.id))
        transformacion.refresh_from_db()
        serializer = self.get_serializer(transformacion)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def descargar(self, request, pk=None):
        from django.http import FileResponse, Http404

        transformacion = self.get_object()
        if not transformacion.descargable:
            raise Http404("El documento aún no está generado.")
        return FileResponse(
            transformacion.archivo_generado.open("rb"),
            as_attachment=True,
            filename=f"{transformacion.nombre_origen}_transformado.xlsx",
        )


class MapeoCampoViewSet(viewsets.ModelViewSet):
    """
    Editar los mapeos de una transformación (correcciones humanas).
      PATCH /api/mapeos/{id}/   cambiar el destino_campo de un mapeo

    Con esto, cuando el usuario corrige a qué campo va una columna en el editor
    de mapeo, el cambio se guarda y se usa al generar el documento.
    """
    serializer_class = MapeoCampoSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        # Solo mapeos de transformaciones de la organización del usuario.
        usuario = self.request.user
        if usuario.es_superadmin:
            qs = MapeoCampo.objects.all()
        else:
            qs = MapeoCampo.objects.filter(
                transformacion__organizacion=usuario.organizacion
            )
        transformacion_id = self.request.query_params.get("transformacion")
        if transformacion_id:
            qs = qs.filter(transformacion_id=transformacion_id)
        return qs.select_related("destino_campo", "transformacion")

    def perform_update(self, serializer):
        # Al corregir a mano, marcar que fue ajuste humano y dejar constancia.
        mapeo = serializer.save(ajustado_por_humano=True)
        Bitacora.objects.create(
            transformacion=mapeo.transformacion,
            evento=Bitacora.Evento.AJUSTE_HUMANO,
            autor=self.request.user,
            detalle={
                "columna_origen": mapeo.origen_columna,
                "nuevo_destino": mapeo.destino_campo.nombre if mapeo.destino_campo else None,
            },
        )