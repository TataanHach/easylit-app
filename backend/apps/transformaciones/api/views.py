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
    """CRUD de transformaciones + acciones del flujo."""

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
        # Si no se eligió empresa, se hereda el mandante de la plantilla.
        mandante = (
            serializer.validated_data.get("mandante")
            or serializer.validated_data["plantilla"].mandante
        )
        transformacion = serializer.save(
            autor=usuario,
            organizacion=usuario.organizacion,
            mandante=mandante,
        )
        Bitacora.objects.create(
            transformacion=transformacion,
            evento=Bitacora.Evento.CARGA,
            autor=usuario,
            detalle={
                "nombre": transformacion.nombre,
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
    def limpiar_ia(self, request, pk=None):
        """Limpia con IA los valores de texto/fecha del origen (no montos)."""
        from apps.transformaciones.services import ia, limpieza
        from apps.transformaciones.models import Bitacora

        from apps.transformaciones.services.errores import mensaje_amigable

        transformacion = self.get_object()
        try:
            df, _ = limpieza.limpiar_excel(
                transformacion.archivo_origen.path,
                transformacion.opciones_limpieza or {},
                todas_las_hojas=True,
            )
        except Exception as e:
            return Response(
                {"detail": mensaje_amigable(e, "procesar")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        primera_fila = df.iloc[0] if len(df) > 0 else None

        valores_campos = []
        indice_a_columna = []
        for mapeo in transformacion.mapeos.select_related("destino_campo").all():
            if mapeo.destino_campo is None:
                continue
            valor = None
            if primera_fila is not None and mapeo.origen_columna in df.columns:
                valor = primera_fila[mapeo.origen_columna]
            valores_campos.append({"campo": mapeo.destino_campo, "valor": valor})
            indice_a_columna.append(mapeo.origen_columna)

        limpios, modelo = ia.limpiar_con_ia(valores_campos)

        valores_ia = {}
        for col, limpio in zip(indice_a_columna, limpios):
            if limpio is not None:
                valores_ia[col] = limpio

        resultado = transformacion.resultado_limpieza or {}
        resultado["valores_ia"] = valores_ia
        transformacion.resultado_limpieza = resultado
        transformacion.save(update_fields=["resultado_limpieza"])

        Bitacora.objects.create(
            transformacion=transformacion,
            evento=Bitacora.Evento.LIMPIEZA,
            autor=request.user,
            detalle={"limpieza_ia": modelo, "campos_limpiados": len(valores_ia)},
        )

        return Response(
            {"ok": True, "modelo": modelo, "campos": len(valores_ia),
             "valores": valores_ia},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def vista_previa(self, request, pk=None):
        """
        Vista previa POR HOJA: devuelve cómo quedará cada hoja del documento.
          - Hojas de formulario: lista de campos (campo -> valor final).
          - Hojas de itemizado: la tabla de partidas (encabezados + filas limpias).
        El frontend muestra una hoja a la vez, navegable con flechas.
        """
        from apps.transformaciones.services import limpieza, generacion
        from apps.transformaciones.tasks import _aplicar_iva
        from openpyxl import load_workbook

        transformacion = self.get_object()
        df, _ = limpieza.limpiar_excel(
            transformacion.archivo_origen.path,
            transformacion.opciones_limpieza or {},
            todas_las_hojas=True,
        )
        primera_fila = df.iloc[0] if len(df) > 0 else None
        valores_ia = (transformacion.resultado_limpieza or {}).get("valores_ia", {})
        iva_por_campo = (transformacion.resultado_limpieza or {}).get("iva_por_campo", {})

        # --- 1. Campos de formulario, agrupados por hoja ---
        campos_por_hoja = {}
        for mapeo in transformacion.mapeos.select_related("destino_campo").all():
            campo = mapeo.destino_campo
            if campo is None:
                continue
            crudo = None
            if primera_fila is not None and mapeo.origen_columna in df.columns:
                crudo = primera_fila[mapeo.origen_columna]
            valor = crudo
            if mapeo.origen_columna in valores_ia:
                valor = valores_ia[mapeo.origen_columna]
            # El IVA elegido en la previsualización REEMPLAZA al de la plantilla.
            if campo.nombre in iva_por_campo:
                ajuste = iva_por_campo[campo.nombre]
            else:
                ajuste = getattr(campo, "ajuste_iva", "") or "NINGUNO"
            valor = _aplicar_iva(valor, ajuste)
            valor_final = generacion.limpiar_valor(valor, campo)

            # ¿Es campo de moneda? (para mostrar el control de IVA)
            formato = getattr(campo, "formato_numero", "") or "NINGUNO"
            es_moneda = formato in ("PESOS", "PESOS_DEC", "UF")

            hoja = campo.hoja_destino or "General"
            campos_por_hoja.setdefault(hoja, []).append({
                "campo": campo.nombre,
                "valor_final": None if valor_final is None else str(valor_final),
                "limpiado_ia": mapeo.origen_columna in valores_ia,
                "es_moneda": es_moneda,
                "ajuste_iva": ajuste,
            })

        # --- 2. Itemizados: leer las tablas del origen y limpiarlas ---
        itemizados_por_hoja = {}
        try:
            ruta_plantilla = transformacion.plantilla.archivo.path
            ruta_origen = transformacion.archivo_origen.path
            wb_dest = load_workbook(ruta_plantilla)
            wb_ori = load_workbook(ruta_origen, data_only=True)

            for nombre_hoja in wb_dest.sheetnames:
                ws_dest = wb_dest[nombre_hoja]
                enc_dest = generacion._detectar_encabezado_tabla(ws_dest)
                if enc_dest is None:
                    continue  # no es hoja de itemizado
                # Buscar la tabla en el origen (misma hoja preferida)
                datos = None
                if nombre_hoja in wb_ori.sheetnames:
                    datos = generacion._leer_itemizado_origen(wb_ori[nombre_hoja])
                if datos is None:
                    for h in wb_ori.sheetnames:
                        d = generacion._leer_itemizado_origen(wb_ori[h])
                        if d:
                            datos = d
                            break
                if not datos:
                    continue

                # Encabezados del destino y emparejar
                _, encabezados_tabla = enc_dest
                cols_dest = [n for n in encabezados_tabla if n]
                mapa = generacion._emparejar_columnas(datos["encabezados"], cols_dest)

                filas_limpias = []
                for partida in datos["partidas"]:
                    fila = []
                    for col_dest in cols_dest:
                        col_ori = mapa.get(col_dest)
                        v = partida.get(col_ori, "") if col_ori else ""
                        v = generacion._limpiar_celda_tabla(v, col_dest)
                        fila.append(str(v) if v is not None else "")
                    filas_limpias.append(fila)

                itemizados_por_hoja[nombre_hoja] = {
                    "columnas": cols_dest,
                    "filas": filas_limpias,
                }
            wb_dest.close()
            wb_ori.close()
        except Exception:
            pass

        # --- 3. Armar la lista de hojas en orden ---
        try:
            wb = load_workbook(transformacion.plantilla.archivo.path, read_only=True)
            orden_hojas = wb.sheetnames
            wb.close()
        except Exception:
            orden_hojas = list(campos_por_hoja.keys()) + list(itemizados_por_hoja.keys())

        hojas = []
        for nombre in orden_hojas:
            if nombre in itemizados_por_hoja:
                hojas.append({
                    "nombre": nombre,
                    "tipo": "itemizado",
                    "tabla": itemizados_por_hoja[nombre],
                })
            elif nombre in campos_por_hoja:
                hojas.append({
                    "nombre": nombre,
                    "tipo": "formulario",
                    "campos": campos_por_hoja[nombre],
                })
        # Campos sin hoja asignada (hoja "General")
        if "General" in campos_por_hoja and not any(h["nombre"] == "General" for h in hojas):
            hojas.append({"nombre": "General", "tipo": "formulario", "campos": campos_por_hoja["General"]})

        return Response({"hojas": hojas}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def ajustar_iva(self, request, pk=None):
        """
        Guarda el ajuste de IVA elegido para un campo en la previsualización.
        Body: { "campo": "Monto_Neto", "ajuste": "AGREGAR" } (o QUITAR, NINGUNO).
        Reemplaza el ajuste de la plantilla para esta transformación.
        """
        transformacion = self.get_object()
        campo = request.data.get("campo")
        ajuste = request.data.get("ajuste", "NINGUNO")
        if not campo:
            return Response(
                {"detail": "No se indicó a qué campo aplicar el IVA. Recarga la página "
                           "e intenta de nuevo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ajuste not in ("NINGUNO", "AGREGAR", "QUITAR"):
            return Response(
                {"detail": f"El ajuste de IVA «{ajuste}» no es válido. Elige Sin IVA, "
                           "+ IVA o Neto."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resultado = transformacion.resultado_limpieza or {}
        iva_campos = resultado.get("iva_por_campo", {})
        iva_campos[campo] = ajuste
        resultado["iva_por_campo"] = iva_campos
        transformacion.resultado_limpieza = resultado
        transformacion.save(update_fields=["resultado_limpieza"])

        return Response({"ok": True, "campo": campo, "ajuste": ajuste},
                        status=status.HTTP_200_OK)

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
        en_proceso = (
            EstadoTransformacion.BORRADOR,
            EstadoTransformacion.LIMPIEZA,
            EstadoTransformacion.MAPEO_PROPUESTO,
        )
        if transformacion.estado in en_proceso:
            return Response(
                {"detail": "La licitación todavía se está procesando. Espera a que "
                           "termine el mapeo y vuelve a intentarlo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not transformacion.mapeos.filter(destino_campo__isnull=False).exists():
            return Response(
                {"detail": "Ningún dato tiene un campo destino asignado, así que el "
                           "documento saldría vacío. En «Mapeo propuesto» elige a qué "
                           "campo de la plantilla va cada dato y vuelve a generar."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transformacion.estado = EstadoTransformacion.APROBADO
        transformacion.save(update_fields=["estado"])
        generar_documento_tarea(str(transformacion.id))
        transformacion.refresh_from_db()

        if transformacion.estado != EstadoTransformacion.GENERADO:
            # La tarea falló: se vuelve a revisión para que el usuario pueda
            # corregir y reintentar, y se responde con el motivo legible.
            motivo = transformacion.detalle_error or (
                "No se pudo generar el documento. Intenta de nuevo; si se repite, "
                "avisa al administrador."
            )
            transformacion.estado = EstadoTransformacion.EN_REVISION
            transformacion.save(update_fields=["estado"])
            return Response({"detail": motivo}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(transformacion)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def descargar(self, request, pk=None):
        from django.http import FileResponse, Http404

        transformacion = self.get_object()
        if not transformacion.descargable:
            raise Http404("El documento aún no está generado. Genera el documento "
                          "desde la revisión y vuelve a descargarlo.")
        if transformacion.nombre:
            nombre_archivo = f"{transformacion.nombre}.xlsx"
        else:
            nombre_archivo = f"{transformacion.nombre_origen}_transformado.xlsx"
        return FileResponse(
            transformacion.archivo_generado.open("rb"),
            as_attachment=True,
            filename=nombre_archivo,
        )


class MapeoCampoViewSet(viewsets.ModelViewSet):
    """Editar los mapeos de una transformación (correcciones humanas)."""
    serializer_class = MapeoCampoSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
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