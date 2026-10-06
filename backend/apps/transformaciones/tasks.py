"""
Tareas asíncronas del worker (Celery).
"""
import re

from celery import shared_task

from .models import Bitacora, EstadoTransformacion, Transformacion


IVA = 1.19


def _a_numero(valor):
    """Convierte a número entendiendo formato chileno y montos sucios."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return None
    # Quitar texto entre paréntesis, ej "(ciento cincuenta millones)".
    s = re.sub(r"\([^)]*\)", "", s)
    # Quitar el ".-" o "-" al final (forma chilena de "pesos justos").
    s = re.sub(r"\.?-\s*$", "", s.strip())
    # Dejar solo dígitos, punto y coma.
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s:
        partes = s.split(".")
        if all(len(g) == 3 for g in partes[1:]):
            s = s.replace(".", "")
        elif len(partes) > 2:
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _aplicar_iva(valor, ajuste):
    """Aplica el ajuste de IVA a un valor monetario, solo si es numérico."""
    if not ajuste or ajuste == "NINGUNO":
        return valor
    num = _a_numero(valor)
    if num is None:
        return valor
    if ajuste == "AGREGAR":
        return round(num * IVA)
    if ajuste == "QUITAR":
        return round(num / IVA)
    return valor


def _plantilla_tiene_tablas(plantilla):
    """True si alguna hoja de la plantilla es una tabla de itemizado (destino)."""
    from openpyxl import load_workbook
    from .services import generacion
    try:
        wb = load_workbook(plantilla.archivo.path)
        hay = any(generacion._detectar_encabezado_tabla(ws) for ws in wb.worksheets)
        wb.close()
        return hay
    except Exception:
        return False


@shared_task
def procesar_transformacion(transformacion_id):
    """Limpia el Excel y pide a la IA el mapeo. Deja todo listo para revisión."""
    from .services import ia, limpieza
    from .services.errores import ErrorUsuario, mensaje_amigable

    try:
        t = Transformacion.objects.select_related("plantilla", "organizacion").get(
            id=transformacion_id
        )
    except Transformacion.DoesNotExist:
        return

    try:
        df, resumen = limpieza.limpiar_excel(
            t.archivo_origen.path, t.opciones_limpieza or {},
            todas_las_hojas=True,
        )
        # Las hojas de itemizado (tablas de partidas) no aparecen en `df`: las
        # copia el generador directo a las hojas de tabla de la plantilla.
        itemizados = limpieza.hojas_itemizado(t.archivo_origen.path)
        sin_formulario = df.empty or len(df.columns) == 0
        if sin_formulario and not itemizados:
            raise ErrorUsuario(
                "No se encontraron datos en el archivo de la licitación. Revisa que "
                "tenga al menos una hoja con encabezados (o etiquetas) y sus valores, "
                "y vuelve a subirlo."
            )
        if not t.plantilla.campos.exists() and not _plantilla_tiene_tablas(t.plantilla):
            raise ErrorUsuario(
                f"La plantilla «{t.plantilla.nombre}» no tiene campos configurados ni "
                "hojas de tabla, así que no hay dónde volcar los datos. Ve a Plantillas, "
                "agrega sus campos y vuelve a crear la transformación."
            )
        resumen["hojas_itemizado"] = itemizados
        t.resultado_limpieza = resumen
        t.estado = EstadoTransformacion.LIMPIEZA
        t.save(update_fields=["resultado_limpieza", "estado"])
        Bitacora.objects.create(
            transformacion=t, evento=Bitacora.Evento.LIMPIEZA, detalle=resumen
        )

        campos = [
            {
                "nombre": c.nombre, "tipo": c.tipo,
                "obligatorio": c.obligatorio, "moneda_destino": c.moneda_destino,
                "descripcion": c.descripcion,
            }
            for c in t.plantilla.campos.all()
        ]
        if sin_formulario:
            # Solo tablas: no hay datos sueltos que mapear (ni que mandar a la IA).
            propuesta, modelo_usado = [], "solo-itemizado"
        else:
            columnas_num = limpieza.detectar_columnas_numericas(df)
            propuesta, modelo_usado = ia.proponer_mapeo(
                df, columnas_num, campos,
                anonimizar=t.organizacion.anonimizar_montos,
            )
        # La IA ya respondió: queda guardar el mapeo (paso "Preparando la revisión").
        if modelo_usado == "heuristica-respaldo":
            # Gemini falló y se usó la coincidencia por nombres: el usuario debe saberlo.
            t.resultado_limpieza["aviso_ia"] = (
                "La IA no estuvo disponible (sin conexión o sin cuota de Gemini), así que "
                "el mapeo se propuso solo por coincidencia de nombres. Revisa cada campo "
                "con más atención antes de generar."
            )
        t.estado = EstadoTransformacion.MAPEO_PROPUESTO
        t.save(update_fields=["estado", "resultado_limpieza"])

        from apps.plantillas.models import CampoPlantilla
        from .models import MapeoCampo

        confianzas = []
        mapeados_ok = 0
        total_campos_plantilla = t.plantilla.campos.count()

        for item in propuesta:
            destino = None
            if item.get("destino"):
                destino = CampoPlantilla.objects.filter(
                    plantilla=t.plantilla, nombre=item["destino"]
                ).first()

            MapeoCampo.objects.create(
                transformacion=t,
                origen_columna=item["origen"],
                destino_campo=destino,
                confianza=item.get("confianza", 0) if destino else 0,
                motivo=item.get("motivo", "") if destino else "Sin campo destino asignado",
            )

            if destino:
                confianzas.append(item.get("confianza", 0))
                mapeados_ok += 1
            else:
                confianzas.append(0)

        # Las columnas de las tablas también cuentan en la confianza: si no, una
        # licitación que solo trae tablas quedaba en 0% aunque calzara perfecto.
        if itemizados:
            from .services import generacion
            tablas = generacion.emparejamiento_tablas(t.plantilla.archivo.path, t.archivo_origen.path)
            for info in tablas.values():
                confianzas.extend(info.pop("puntajes"))
            t.resultado_limpieza["tablas_emparejadas"] = tablas

        t.confianza = int(sum(confianzas) / len(confianzas)) if confianzas else 0
        t.estado = EstadoTransformacion.EN_REVISION
        t.save(update_fields=["confianza", "estado", "resultado_limpieza"])
        Bitacora.objects.create(
            transformacion=t, evento=Bitacora.Evento.MAPEO_IA,
            detalle={
                "modelo": modelo_usado,
                "columnas_origen": len(propuesta),
                "campos_mapeados": mapeados_ok,
                "campos_plantilla": total_campos_plantilla,
                "confianza_global": t.confianza,
            },
        )

    except Exception as e:
        t.estado = EstadoTransformacion.ERROR
        t.detalle_error = mensaje_amigable(e, "procesar")[:500]
        t.save(update_fields=["estado", "detalle_error"])
        Bitacora.objects.create(
            transformacion=t, evento=Bitacora.Evento.ERROR, detalle={"error": str(e)[:500]}
        )


@shared_task
def generar_documento_tarea(transformacion_id):
    """Genera el Excel final tras la aprobación del mapeo."""
    from django.core.files.base import ContentFile
    from .services import generacion, limpieza
    from .services.errores import mensaje_amigable

    try:
        t = Transformacion.objects.select_related("plantilla").get(id=transformacion_id)
    except Transformacion.DoesNotExist:
        return

    try:
        df, _ = limpieza.limpiar_excel(
            t.archivo_origen.path, t.opciones_limpieza or {},
            todas_las_hojas=True,
        )
        primera_fila = df.iloc[0] if len(df) > 0 else None

      # Valores limpios por IA (Capa 2), si el usuario los generó.
        valores_ia = (t.resultado_limpieza or {}).get("valores_ia", {})
 
        mapeos_con_valor = []
        con_valor = 0
        for mapeo in t.mapeos.select_related("destino_campo").all():
            campo = mapeo.destino_campo
            if campo is None:
                continue
            valor = None
            if primera_fila is not None and mapeo.origen_columna in df.columns:
                valor = primera_fila[mapeo.origen_columna]
 
            # Si la IA limpió este valor, usar el limpio en vez del original.
            if mapeo.origen_columna in valores_ia:
                valor = valores_ia[mapeo.origen_columna]
 
            # El IVA de la previsualizacion reemplaza al de la plantilla.
            iva_por_campo = (t.resultado_limpieza or {}).get("iva_por_campo", {})
            if campo.nombre in iva_por_campo:
                ajuste = iva_por_campo[campo.nombre]
            else:
                ajuste = getattr(campo, "ajuste_iva", "") or "NINGUNO"
            valor = _aplicar_iva(valor, ajuste)

            if valor is not None and str(valor).strip() != "":
                con_valor += 1
            mapeos_con_valor.append({"campo": campo, "valor": valor})

        contenido = generacion.generar_documento(
            t.plantilla.archivo.path, mapeos_con_valor,
            ruta_origen=t.archivo_origen.path,
            calcular_totales=bool((t.resultado_limpieza or {}).get("calcular_totales")),
            valores_ia_tablas=(t.resultado_limpieza or {}).get("valores_ia_tablas"),
        )

        nombre = f"generado_{t.id}.xlsx"
        t.archivo_generado.save(nombre, ContentFile(contenido), save=False)
        t.estado = EstadoTransformacion.GENERADO
        t.detalle_error = ""   # por si un intento anterior había fallado
        t.save(update_fields=["archivo_generado", "estado", "detalle_error"])
        Bitacora.objects.create(
            transformacion=t, evento=Bitacora.Evento.GENERACION,
            detalle={
                "archivo": nombre,
                "campos_con_destino": len(mapeos_con_valor),
                "campos_con_valor": con_valor,
            },
        )
    except Exception as e:
        t.estado = EstadoTransformacion.ERROR
        t.detalle_error = mensaje_amigable(e, "generar")[:500]
        t.save(update_fields=["estado", "detalle_error"])
        Bitacora.objects.create(
            transformacion=t, evento=Bitacora.Evento.ERROR, detalle={"error": str(e)[:400]}
        )