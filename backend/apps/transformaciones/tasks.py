"""
Tareas asíncronas del worker (Celery).

Procesar un Excel puede tardar bastante, así que corre aquí, fuera del ciclo
HTTP. La vista dispara la tarea y responde de inmediato; el worker hace el trabajo
pesado y actualiza el estado de la transformación, que el frontend consulta por
polling.

Flujo: LIMPIEZA (pandas) → MAPEO_PROPUESTO (Gemini) → EN_REVISION (espera humano).
La generación del archivo final ocurre tras la aprobación, en otra tarea.
"""
from celery import shared_task

from .models import Bitacora, EstadoTransformacion, Transformacion


@shared_task
def procesar_transformacion(transformacion_id):
    """Limpia el Excel y pide a la IA el mapeo. Deja todo listo para revisión."""
    from .services import ia, limpieza

    try:
        t = Transformacion.objects.select_related("plantilla", "organizacion").get(
            id=transformacion_id
        )
    except Transformacion.DoesNotExist:
        return

    try:
        # 1. Limpieza determinista con pandas.
        df, resumen = limpieza.limpiar_excel(
            t.archivo_origen.path, t.opciones_limpieza or {}
        )
        columnas_num = limpieza.detectar_columnas_numericas(df)
        t.resultado_limpieza = resumen
        t.estado = EstadoTransformacion.LIMPIEZA
        t.save(update_fields=["resultado_limpieza", "estado"])
        Bitacora.objects.create(
            transformacion=t, evento=Bitacora.Evento.LIMPIEZA, detalle=resumen
        )

        # 2. Propuesta de mapeo con IA (sobre datos anonimizados si corresponde).
        campos = [
            {
                "nombre": c.nombre, "tipo": c.tipo,
                "obligatorio": c.obligatorio, "moneda_destino": c.moneda_destino,
                "descripcion": c.descripcion,
            }
            for c in t.plantilla.campos.all()
        ]
        propuesta, modelo_usado = ia.proponer_mapeo(
            df, columnas_num, campos,
            anonimizar=t.organizacion.anonimizar_montos,
        )

        # 3. Guardar los mapeos propuestos.
        from apps.plantillas.models import CampoPlantilla
        from .models import MapeoCampo

        # La confianza global ahora refleja la REALIDAD, no solo lo que dijo la
        # IA. Un mapeo cuya columna no encontró campo destino (destino = None)
        # NO se puede rellenar, así que cuenta como 0, no se ignora.
        #
        # Antes: se promediaba solo la confianza de la IA, así que salía alto
        # (ej. 98%) aunque las celdas quedaran vacías. Eso engañaba al usuario.
        # Ahora: si la mitad no se mapeó, la confianza baja y avisa que algo pasó.
        confianzas = []
        mapeados_ok = 0            # cuántos tienen destino real
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
                # Si no hay destino real, la confianza mostrada del mapeo es 0,
                # para que el usuario vea de inmediato cuáles no se asignaron.
                confianza=item.get("confianza", 0) if destino else 0,
                motivo=item.get("motivo", "") if destino else "Sin campo destino asignado",
            )

            if destino:
                confianzas.append(item.get("confianza", 0))
                mapeados_ok += 1
            else:
                confianzas.append(0)  # cuenta como 0 en el promedio

        # Confianza global: promedio real (los no mapeados arrastran hacia abajo).
        t.confianza = int(sum(confianzas) / len(confianzas)) if confianzas else 0
        t.estado = EstadoTransformacion.EN_REVISION
        t.save(update_fields=["confianza", "estado"])
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
        t.detalle_error = str(e)[:500]
        t.save(update_fields=["estado", "detalle_error"])
        Bitacora.objects.create(
            transformacion=t, evento=Bitacora.Evento.ERROR, detalle={"error": str(e)[:500]}
        )


@shared_task
def generar_documento_tarea(transformacion_id):
    """
    Genera el Excel final tras la aprobación del mapeo.

    Toma cada mapeo aprobado, lee el valor correspondiente del origen, y lo
    escribe en la plantilla destino preservando el formato. Guarda el resultado
    en archivo_generado y marca la transformación como GENERADO.
    """
    from django.core.files.base import ContentFile
    from .services import generacion, limpieza

    try:
        t = Transformacion.objects.select_related("plantilla").get(id=transformacion_id)
    except Transformacion.DoesNotExist:
        return

    try:
        # Leer el origen ya limpio para obtener los valores.
        df, _ = limpieza.limpiar_excel(t.archivo_origen.path, t.opciones_limpieza or {})
        primera_fila = df.iloc[0] if len(df) > 0 else None

        # Construir la lista campo→valor a partir de los mapeos aprobados.
        # Contamos cuántos de verdad tienen un valor, para reportarlo.
        mapeos_con_valor = []
        con_valor = 0
        for mapeo in t.mapeos.select_related("destino_campo").all():
            if mapeo.destino_campo is None:
                continue
            valor = None
            if primera_fila is not None and mapeo.origen_columna in df.columns:
                valor = primera_fila[mapeo.origen_columna]
            if valor is not None and str(valor).strip() != "":
                con_valor += 1
            mapeos_con_valor.append({"campo": mapeo.destino_campo, "valor": valor})

        # Generar el Excel.
        contenido = generacion.generar_documento(t.plantilla.archivo.path, mapeos_con_valor)

        # Guardar el resultado.
        nombre = f"generado_{t.id}.xlsx"
        t.archivo_generado.save(nombre, ContentFile(contenido), save=False)
        t.estado = EstadoTransformacion.GENERADO
        t.save(update_fields=["archivo_generado", "estado"])
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
        t.detalle_error = f"Error al generar: {str(e)[:400]}"
        t.save(update_fields=["estado", "detalle_error"])
        Bitacora.objects.create(
            transformacion=t, evento=Bitacora.Evento.ERROR, detalle={"error": str(e)[:400]}
        )