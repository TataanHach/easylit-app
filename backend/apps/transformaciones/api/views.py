"""
Vistas de transformaciones.

Dos reglas de oro que se aplican en TODAS las consultas:

  1. Aislamiento por organización: un usuario solo ve datos de SU organización.
  2. Alcance por autor: el parámetro ?alcance= filtra Mías / Equipo / Todas.
"""
from django.conf import settings
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.common.archivos import ruta_local
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
                ruta_local(transformacion.archivo_origen),
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

        # Textos de las tablas (itemizado): solo columnas de texto/fecha, sin repetidos.
        from types import SimpleNamespace
        from openpyxl import load_workbook
        from apps.transformaciones.services import generacion

        textos_tabla = []
        try:
            ruta = ruta_local(transformacion.archivo_origen)
            wb_ori = load_workbook(ruta, data_only=True, read_only=True)
            for nombre in limpieza.hojas_itemizado(ruta):
                datos = generacion._leer_itemizado_origen(wb_ori[nombre])
                if datos:
                    tope = settings.IA_MAX_TEXTOS_TABLA
                    textos_tabla += generacion.textos_para_ia(datos, maximo=tope - len(textos_tabla))
                if len(textos_tabla) >= settings.IA_MAX_TEXTOS_TABLA:
                    break
            wb_ori.close()
        except Exception:
            textos_tabla = []
        for _clave, col, tipo, valor in textos_tabla:
            pseudo = SimpleNamespace(nombre=col, tipo=tipo, formato_numero="NINGUNO")
            valores_campos.append({"campo": pseudo, "valor": valor})

        # Huella de lo que se le enviaría a la IA. Si es la misma de la última
        # limpieza buena, se devuelve ese resultado sin volver a llamar a la IA:
        # así apretar el botón dos veces dice lo mismo y no gasta cuota.
        import hashlib
        import json as _json
        huella = hashlib.sha256(_json.dumps(
            [[getattr(v["campo"], "nombre", ""), str(v["valor"])] for v in valores_campos],
            ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        previo = transformacion.resultado_limpieza or {}
        if previo.get("ia_huella") == huella and previo.get("ia_respuesta"):
            return Response({**previo["ia_respuesta"], "repetida": True}, status=status.HTTP_200_OK)

        # Una sola llamada a la IA para campos y tablas.
        limpios, modelo = ia.limpiar_con_ia(valores_campos)
        n_campos = len(indice_a_columna)

        # Si la IA falló o no está configurada, devuelve los valores originales:
        # guardarlos borraría una limpieza buena hecha antes. Se avisa y no se toca nada.
        if modelo in ("sin-clave-ia", "limpieza-ia-fallo", "limpieza-ia-sin-formato"):
            return Response(
                {"ok": False, "modelo": modelo,
                 "conserva_anterior": bool(previo.get("valores_ia") or previo.get("valores_ia_tablas"))},
                status=status.HTTP_200_OK,
            )

        def corto(v):
            texto = "" if v is None else str(v).strip()
            return texto if len(texto) <= 60 else texto[:57] + "…"

        # `cambios`: qué cambió la IA (antes → después), para mostrárselo al usuario.
        valores_ia, campos_cambiados, cambios = {}, 0, []
        for i, col in enumerate(indice_a_columna):
            limpio = limpios[i]
            if limpio is not None:
                valores_ia[col] = limpio
                antes = valores_campos[i]["valor"]
                if str(limpio).strip() != str(antes).strip():
                    campos_cambiados += 1
                    cambios.append({"campo": valores_campos[i]["campo"].nombre,
                                    "antes": corto(antes), "despues": corto(limpio)})

        valores_ia_tablas, celdas_cambiadas, cambios_tabla = {}, 0, []
        for (clave, col, _tipo, original), limpio in zip(textos_tabla, limpios[n_campos:]):
            if limpio is not None and str(limpio).strip() != original:
                valores_ia_tablas.setdefault(clave, {})[original] = str(limpio).strip()
                celdas_cambiadas += 1
                cambios_tabla.append({"campo": col, "antes": corto(original), "despues": corto(limpio)})

        respuesta = {
            "ok": True, "modelo": modelo, "campos": campos_cambiados,
            "campos_revisados": n_campos,
            "textos_tabla": celdas_cambiadas, "textos_tabla_revisados": len(textos_tabla),
            "valores": valores_ia, "cambios": cambios, "cambios_tabla": cambios_tabla,
        }
        resultado = transformacion.resultado_limpieza or {}
        resultado["valores_ia"] = valores_ia
        resultado["valores_ia_tablas"] = valores_ia_tablas
        resultado["ia_huella"] = huella
        resultado["ia_respuesta"] = respuesta
        transformacion.resultado_limpieza = resultado
        transformacion.save(update_fields=["resultado_limpieza"])

        Bitacora.objects.create(
            transformacion=transformacion,
            evento=Bitacora.Evento.LIMPIEZA,
            autor=request.user,
            detalle={"limpieza_ia": modelo, "campos_limpiados": campos_cambiados,
                     "textos_tabla_enviados": len(textos_tabla),
                     "textos_tabla_limpiados": celdas_cambiadas},
        )

        return Response(respuesta, status=status.HTTP_200_OK)

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
            ruta_local(transformacion.archivo_origen),
            transformacion.opciones_limpieza or {},
            todas_las_hojas=True,
        )
        primera_fila = df.iloc[0] if len(df) > 0 else None
        valores_ia = (transformacion.resultado_limpieza or {}).get("valores_ia", {})
        iva_por_campo = (transformacion.resultado_limpieza or {}).get("iva_por_campo", {})

        # --- 1. Campos de formulario, agrupados por hoja ---
        campos_por_hoja = {}
        valores_por_campo = {}
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
            valores_por_campo[campo.id] = valor
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

        # Lo que quedará vacío en el documento y por qué. Mismo cálculo que al
        # generar, para que el usuario lo vea ANTES y no se entere después.
        try:
            estados = generacion.estado_campos(
                ruta_local(transformacion.plantilla.archivo),
                list(transformacion.plantilla.campos.all()), valores_por_campo,
                transformacion.plantilla.tipos_hoja,
            )
        except Exception:
            estados = []
        avisos = [e["aviso"] for e in estados if e["aviso"]]
        # Resumen campo por campo (hoja, valor final y si se llenará), para la
        # ventana de resultado del frontend.
        campos_estado = [
            {"campo": e["campo"].nombre, "hoja": e["hoja"], "ok": not e["aviso"],
             "valor": "" if e["aviso"] else str(generacion.limpiar_valor(
                 valores_por_campo.get(e["campo"].id), e["campo"]))[:60]}
            for e in estados
        ]

        # --- 2. Itemizados: leer las tablas del origen y limpiarlas ---
        itemizados_por_hoja = {}
        try:
            ruta_plantilla = ruta_local(transformacion.plantilla.archivo)
            ruta_origen = ruta_local(transformacion.archivo_origen)
            wb_dest = generacion.abrir_plantilla(ruta_plantilla, transformacion.plantilla.tipos_hoja)
            wb_ori = load_workbook(ruta_origen, data_only=True, read_only=True)

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
                    avisos.append(generacion.aviso_tabla_sin_origen(nombre_hoja))
                    continue

                # Encabezados del destino; filas limpias (y totales si se pidió).
                _, encabezados_tabla = enc_dest
                cols_dest = [n for n in encabezados_tabla if n]
                calcular = bool((transformacion.resultado_limpieza or {}).get("calcular_totales"))
                ia_tablas = (transformacion.resultado_limpieza or {}).get("valores_ia_tablas")
                filas, faltantes = generacion.filas_itemizado(datos, cols_dest, calcular, ia_tablas)

                filas_limpias, calculadas, por_ia = [], [], []
                for i, (valores, calc, ia_cols) in enumerate(filas):
                    filas_limpias.append([generacion.texto_celda_tabla(valores[c], c) for c in cols_dest])
                    calculadas += [[i, cols_dest.index(c)] for c in calc]
                    por_ia += [[i, cols_dest.index(c)] for c in ia_cols]

                itemizados_por_hoja[nombre_hoja] = {
                    "columnas": cols_dest,
                    "filas": filas_limpias,
                    "totales_faltantes": faltantes,      # filas sin total con precio y cantidad
                    "totales_calculados": calcular,
                    "celdas_calculadas": calculadas,     # [fila, columna] marcadas en la vista
                    "celdas_ia": por_ia,                 # [fila, columna] limpiadas por la IA
                }
            wb_dest.close()
            wb_ori.close()
        except Exception:
            avisos.append(generacion.AVISO_TABLAS_FALLARON)

        # --- 3. Armar la lista de hojas en orden ---
        try:
            wb = load_workbook(ruta_local(transformacion.plantilla.archivo), read_only=True)
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
                    "campos": campos_por_hoja.get(nombre, []),
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

        # --- 4. Datos del origen con su valor, para elegir cuál va en cada campo ---
        datos_origen = []
        for mapeo in transformacion.mapeos.all().order_by("origen_columna"):
            valor = None
            if primera_fila is not None and mapeo.origen_columna in df.columns:
                valor = primera_fila[mapeo.origen_columna]
            if mapeo.origen_columna in valores_ia:
                valor = valores_ia[mapeo.origen_columna]
            texto = "" if valor is None or str(valor) == "nan" else str(valor).strip()
            datos_origen.append({"columna": mapeo.origen_columna, "valor": texto[:80]})

        return Response({"hojas": hojas, "datos_origen": datos_origen, "avisos": avisos,
                         "campos_estado": campos_estado},
                        status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def asignar_dato(self, request, pk=None):
        """
        Elige qué dato del origen rellena un campo de la plantilla.
        Body: { "campo": "<id CampoPlantilla>", "origen_columna": "RUT oferente" }
        (origen_columna null/"" = dejar el campo sin dato).

        Cada dato del origen va a un solo campo: si el elegido ya rellenaba otro
        campo, se mueve, y la respuesta lo indica en `quitado_de`.
        """
        from django.db import transaction as db_transaction
        from apps.plantillas.models import CampoPlantilla

        transformacion = self.get_object()
        campo_id = request.data.get("campo")
        columna = (request.data.get("origen_columna") or "").strip() or None

        campo = CampoPlantilla.objects.filter(
            id=campo_id, plantilla=transformacion.plantilla
        ).first()
        if campo is None:
            return Response(
                {"detail": "Ese campo no pertenece a la plantilla de esta transformación. "
                           "Recarga la página e intenta de nuevo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mapeos = transformacion.mapeos.select_related("destino_campo")
        elegido = None
        if columna:
            elegido = mapeos.filter(origen_columna=columna).first()
            if elegido is None:
                return Response(
                    {"detail": f"El dato «{columna}» no existe en el archivo de origen. "
                               "Recarga la página e intenta de nuevo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        quitado_de = None
        with db_transaction.atomic():
            # Los datos que rellenaban este campo dejan de hacerlo.
            anteriores = list(mapeos.filter(destino_campo=campo).exclude(
                id=elegido.id if elegido else None
            ))
            for m in anteriores:
                m.destino_campo = None
                m.ajustado_por_humano = True
                m.save(update_fields=["destino_campo", "ajustado_por_humano"])

            if elegido and elegido.destino_campo_id != campo.id:
                if elegido.destino_campo_id:
                    quitado_de = elegido.destino_campo.nombre
                elegido.destino_campo = campo
                elegido.ajustado_por_humano = True
                elegido.save(update_fields=["destino_campo", "ajustado_por_humano"])

            Bitacora.objects.create(
                transformacion=transformacion,
                evento=Bitacora.Evento.AJUSTE_HUMANO,
                autor=request.user,
                detalle={
                    "campo": campo.nombre,
                    "dato": columna,
                    "dato_anterior": [m.origen_columna for m in anteriores],
                    "quitado_de": quitado_de,
                },
            )

        return Response(
            {
                "mapeos": MapeoCampoSerializer(transformacion.mapeos.all(), many=True).data,
                "quitado_de": quitado_de,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def calcular_totales(self, request, pk=None):
        """
        Activa o quita el cálculo de totales faltantes en las tablas
        (total = precio × cantidad). Body: { "activar": true | false }.
        """
        transformacion = self.get_object()
        activar = bool(request.data.get("activar", True))
        resultado = transformacion.resultado_limpieza or {}
        resultado["calcular_totales"] = activar
        transformacion.resultado_limpieza = resultado
        transformacion.save(update_fields=["resultado_limpieza"])
        Bitacora.objects.create(
            transformacion=transformacion,
            evento=Bitacora.Evento.AJUSTE_HUMANO,
            autor=request.user,
            detalle={"calcular_totales": activar},
        )
        return Response({"ok": True, "activar": activar}, status=status.HTTP_200_OK)

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
        hay_itemizado = bool((transformacion.resultado_limpieza or {}).get("hojas_itemizado"))
        if not hay_itemizado and not transformacion.mapeos.filter(destino_campo__isnull=False).exists():
            return Response(
                {"detail": "Ningún campo tiene un dato asignado, así que el documento "
                           "saldría vacío. En «Mapeo propuesto» elige qué dato del Excel "
                           "va en cada campo y vuelve a generar."},
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

        # Lo que no se pudo escribir, para avisar aunque la generación funcionó.
        evento = transformacion.bitacora.filter(evento=Bitacora.Evento.GENERACION).last()
        data = dict(self.get_serializer(transformacion).data)
        data["avisos"] = (evento.detalle.get("avisos", []) if evento else [])
        return Response(data, status=status.HTTP_200_OK)

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