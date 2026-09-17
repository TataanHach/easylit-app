/**
 * Servicio de plantillas.
 *
 * Por ahora solo lo que el wizard necesita: listar las plantillas de la
 * organización para elegir el formato destino. La gestión completa (crear,
 * editar) se añade cuando construyamos la biblioteca de plantillas.
 */
import { api } from "@/api/client";
import type { Plantilla } from "@/types";

export const plantillaService = {
  async listar(): Promise<Plantilla[]> {
    const { data } = await api.get<Plantilla[]>("/plantillas/");
    return data;
  },

  async detalle(id: string): Promise<Plantilla> {
    const { data } = await api.get<Plantilla>(`/plantillas/${id}/`);
    return data;
  },
  async hojas(id: string): Promise<{ hojas: string[] }> {
      const { data } = await api.get(`/plantillas/${id}/hojas/`);
      return data;
    },

  /** Crea una plantilla. Incluye el archivo, así que va como multipart. */
  async crear(payload: {
    nombre: string;
    mandante?: string;
    sector?: string;
    formato: string;
    archivo: File;
  }): Promise<Plantilla> {
    const form = new FormData();
    form.append("nombre", payload.nombre);
    if (payload.mandante) form.append("mandante", payload.mandante);
    if (payload.sector) form.append("sector", payload.sector);
    form.append("formato", payload.formato);
    form.append("archivo", payload.archivo);
    const { data } = await api.post<Plantilla>("/plantillas/", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },

  /** Edita los datos de una plantilla (sin cambiar el archivo). */
  async editar(id: string, payload: {
    nombre: string;
    mandante?: string;
    sector?: string;
  }): Promise<Plantilla> {
    const { data } = await api.patch<Plantilla>(`/plantillas/${id}/`, payload);
    return data;
  },

  /** Elimina una plantilla. */
  async eliminar(id: string): Promise<void> {
    await api.delete(`/plantillas/${id}/`);
  },
};

// --- Gestión de campos de una plantilla ---
export interface CampoInput {
  plantilla: string;
  nombre: string;
  tipo: string;
  etiqueta_busqueda?: string;
  obligatorio?: boolean;
  orden?: number;
  formato_numero?: string;
  hoja_destino?: string;
}
export const campoService = {
  async listar(plantillaId: string) {
    const { data } = await api.get(`/campos/?plantilla=${plantillaId}`);
    return data as any[];
  },
  async crear(payload: CampoInput) {
    const { data } = await api.post("/campos/", payload);
    return data;
  },
  async editar(id: string, payload: Partial<CampoInput>) {
    const { data } = await api.patch(`/campos/${id}/`, payload);
    return data;
  },
  async eliminar(id: string) {
    await api.delete(`/campos/${id}/`);
  },
};