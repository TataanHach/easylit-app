/**
 * Servicio de transformaciones.
 *
 * Llamadas al backend del bloque 3. El parámetro `alcance` es el que alimenta el
 * filtro Mías / De mi equipo / Todas del historial.
 */
import { api } from "@/api/client";
import type { Transformacion } from "@/types";

export type Alcance = "mine" | "team" | "all";

export const transformacionService = {
  async listar(alcance: Alcance = "mine"): Promise<Transformacion[]> {
    const { data } = await api.get<Transformacion[]>("/transformaciones/", {
      params: { alcance },
    });
    return data;
  },
  /** Ajusta el IVA de un campo en la previsualización. */
  async ajustarIVA(id: string, campo: string, ajuste: string) {
    const { data } = await api.post(`/transformaciones/${id}/ajustar_iva/`, {
      campo, ajuste,
    });
    return data;
  },

  async detalle(id: string): Promise<Transformacion> {
    const { data } = await api.get<Transformacion>(`/transformaciones/${id}/`);
    return data;
  },

  /** Aprueba el mapeo propuesto. */
  async aprobar(id: string): Promise<Transformacion> {
    const { data } = await api.post<Transformacion>(`/transformaciones/${id}/aprobar/`);
    return data;
  },

  /** Dispara la generación del documento final. */
  async generar(id: string): Promise<Transformacion> {
    const { data } = await api.post<Transformacion>(`/transformaciones/${id}/generar/`);
    return data;
  },

  /**
   * Descarga el documento generado. Lo pide con el token (vía el cliente axios)
   * y lo entrega como archivo. NO se puede abrir la URL directa en una pestaña
   * porque esa petición no lleva el token y el backend responde 401.
   */
  async descargar(id: string, nombreArchivo: string): Promise<void> {
    const resp = await api.get(`/transformaciones/${id}/descargar/`, {
      responseType: "blob",
    });
    // Crear un enlace temporal en memoria y forzar la descarga.
    const url = window.URL.createObjectURL(new Blob([resp.data]));
    const a = document.createElement("a");
    a.href = url;
    a.download = nombreArchivo;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },

  /** Elimina una transformación (solo el autor o un gerente/superadmin). */
  async eliminar(id: string): Promise<void> {
    await api.delete(`/transformaciones/${id}/`);
  },

  /**
   * Crea una transformación subiendo el Excel origen y eligiendo la plantilla.
   * Va como multipart/form-data porque incluye un archivo.
   */
  async crear(payload: {
    archivo: File;
    plantilla: string;
    mandante?: string;
    nombre?: string;
  }): Promise<Transformacion> {
    const form = new FormData();
    form.append("archivo_origen", payload.archivo);
    form.append("nombre_origen", payload.archivo.name);
    form.append("plantilla", payload.plantilla);
    if (payload.mandante) form.append("mandante", payload.mandante);
    if (payload.nombre) form.append("nombre", payload.nombre);

    const { data } = await api.post<Transformacion>("/transformaciones/", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
  /**
   * Elige qué dato del origen rellena un campo de la plantilla (null = sin dato).
   * Si el dato ya estaba en otro campo, se mueve: `quitado_de` dice de cuál.
   */
  async asignarDato(id: string, campoId: string, origenColumna: string | null) {
    const { data } = await api.post(`/transformaciones/${id}/asignar_dato/`, {
      campo: campoId, origen_columna: origenColumna,
    });
    return data as { mapeos: any[]; quitado_de: string | null };
  },

  /** Calcula (o deja de calcular) los totales faltantes de las tablas: precio × cantidad. */
  async calcularTotales(id: string, activar: boolean) {
    const { data } = await api.post(`/transformaciones/${id}/calcular_totales/`, { activar });
    return data;
  },

  /** Cambia el campo destino de un mapeo (corrección humana). */
  async editarMapeo(mapeoId: string, destinoCampoId: string | null) {
    const { data } = await api.patch(`/mapeos/${mapeoId}/`, {
      destino_campo: destinoCampoId,
    });
    return data;
  },

  /** Limpia con IA los valores de texto/fecha (no montos). Opcional. */
  async limpiarIA(id: string) {
    const { data } = await api.post(`/transformaciones/${id}/limpiar_ia/`);
    return data;  // { ok, modelo, campos, valores }
  },
  /** Vista previa de los valores finales (cómo quedarán en el documento). */
  async vistaPrevia(id: string) {
    const { data } = await api.get(`/transformaciones/${id}/vista_previa/`);
    return data;  // { filas: [{campo, hoja, valor_crudo, valor_final, limpiado_ia}] }
  },

};
