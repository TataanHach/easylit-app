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
  }): Promise<Transformacion> {
    const form = new FormData();
    form.append("archivo_origen", payload.archivo);
    form.append("nombre_origen", payload.archivo.name);
    form.append("plantilla", payload.plantilla);
    if (payload.mandante) form.append("mandante", payload.mandante);

    const { data } = await api.post<Transformacion>("/transformaciones/", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
};