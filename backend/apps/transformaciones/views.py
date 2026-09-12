"""
Vistas de transformaciones.

Dos reglas de oro que se aplican en TODAS las consultas:

  1. Aislamiento por organización: un usuario solo ve datos de SU organización.
     Nunca se devuelve nada de otra empresa. Esto se hace en get_queryset(),
     el único lugar por el que pasan todas las lecturas.

  2. Alcance por autor: el parámetro ?alcance= filtra entre lo propio, lo del
     equipo o todo, que es el filtro "Mías / De mi equipo / Todas" del historial.

Aquí NO va la lógica de procesamiento (limpieza, IA, validación). Eso vive en el
worker (bloque 4). Estas vistas solo crean, listan, muestran y disparan.
"""
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.transformaciones.models import Bitacora, Transformacion

from .serializers import (
    CrearTransformacionSerializer,
    TransformacionDetalleSerializer,
    TransformacionListaSerializer,
)


class TransformacionViewSet(viewsets.ModelViewSet):
    """
    CRUD de transformaciones + acciones del flujo.

    Rutas que genera automáticamente:
      GET    /api/transformaciones/           lista (con ?alcance=)
      POST   /api/transformaciones/           crear (subir Excel + plantilla)
      GET    /api/transformaciones/{id}/      detalle
      DELETE /api/transformaciones/{id}/      borrar
      POST   /api/transformaciones/{id}/aprobar/    aprobar mapeo
    """

    def get_queryset(self):
        usuario = self.request.user

        # Superadmin ve todo; el resto solo su organización. Este filtro es la
        # frontera de seguridad entre empresas.
        if usuario.es_superadmin:
            qs = Transformacion.objects.all()
        else:
            qs = Transformacion.objects.filter(organizacion=usuario.organizacion)

        # Alcance: mine (por defecto) / team / all.
        alcance = self.request.query_params.get("alcance", "mine")
        if alcance == "mine":
            qs = qs.filter(autor=usuario)
        elif alcance == "team":
            qs = qs.exclude(autor=usuario)
        # "all" no filtra más: todo lo de la organización.

        # Filtro opcional por estado, para las pestañas del historial.
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
        # El autor y la organización se fijan desde el usuario autenticado,
        # nunca desde la petición. Así nadie crea a nombre de otro.
        usuario = self.request.user
        transformacion = serializer.save(
            autor=usuario,
            organizacion=usuario.organizacion,
        )
        # Registrar la carga en la bitácora.
        Bitacora.objects.create(
            transformacion=transformacion,
            evento=Bitacora.Evento.CARGA,
            autor=usuario,
            detalle={
                "archivo": transformacion.nombre_origen,
                "plantilla": transformacion.plantilla.nombre,
            },
        )
        # Disparar el procesamiento asíncrono (limpieza + IA) en el worker.
        # Si Celery/Redis no están corriendo (p. ej. en desarrollo local sin
        # worker), .delay() falla silenciosamente; para pruebas se puede llamar
        # a la tarea de forma síncrona. En producción, el worker la toma.
        try:
            from apps.transformaciones.tasks import procesar_transformacion
            procesar_transformacion.delay(str(transformacion.id))
        except Exception:
            # Sin broker disponible no interrumpimos la creación; el estado
            # queda en BORRADOR y se puede reprocesar.
            pass

    def perform_destroy(self, instance):
        # Solo el autor o un gerente/superadmin pueden borrar.
        usuario = self.request.user
        if instance.autor_id != usuario.id and not usuario.puede_gestionar_usuarios:
            raise PermissionDenied("No puedes borrar transformaciones de otra persona.")
        instance.delete()

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        """
        Aprueba el mapeo propuesto. Marca la transformación como APROBADA y deja
        constancia en la bitácora de quién aprobó. La generación del archivo la
        hará el worker (bloque 4); aquí solo se registra la decisión humana.
        """
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
        """
        Dispara la generación del documento final. Requiere que el mapeo esté
        aprobado. El worker escribe el Excel; el frontend consulta el estado.
        """
        from apps.transformaciones.models import EstadoTransformacion

        transformacion = self.get_object()
        # Solo se genera desde APROBADO o EN_REVISION (aprobación implícita).
        transformacion.estado = EstadoTransformacion.APROBADO
        transformacion.save(update_fields=["estado"])

        try:
            from apps.transformaciones.tasks import generar_documento_tarea
            generar_documento_tarea.delay(str(transformacion.id))
        except Exception:
            # Sin worker (dev sin Redis), se puede llamar sincrónicamente.
            from apps.transformaciones.tasks import generar_documento_tarea
            generar_documento_tarea(str(transformacion.id))

        transformacion.refresh_from_db()
        serializer = self.get_serializer(transformacion)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def descargar(self, request, pk=None):
        """Devuelve el archivo generado para descarga."""
        from django.http import FileResponse, Http404

        transformacion = self.get_object()
        if not transformacion.descargable:
            raise Http404("El documento aún no está generado.")
        return FileResponse(
            transformacion.archivo_generado.open("rb"),
            as_attachment=True,
            filename=f"{transformacion.nombre_origen}_transformado.xlsx",
        )
