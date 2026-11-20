/**
 * Servicio del equipo: lo usa el gerente para ver a su gente e invitar
 * colaboradores. EasyLit no envía correos: el gerente copia el mensaje con el
 * código y se lo hace llegar al colaborador (WhatsApp, correo, etc.).
 */
import { api } from "@/api/client";
import type { Rol } from "@/types";

export type EstadoAcceso = "ACTIVO" | "PENDIENTE" | "VENCIDA" | "SIN_INVITACION" | "DESACTIVADO";

export interface MiembroEquipo {
  id: string;
  nombre_completo: string;
  email: string;
  rut: string;
  rol: Rol;
  estado: EstadoAcceso;
  expira: string | null;
}

/** El código (K7M2-QX9P) llega solo al invitar o al generar uno nuevo: no se puede volver a pedir. */
export interface CodigoInvitacion {
  codigo: string;
  expira: string;
}

export const equipoService = {
  async listar(): Promise<MiembroEquipo[]> {
    const { data } = await api.get<MiembroEquipo[]>("/auth/equipo/");
    return data;
  },

  /** Crea al colaborador (sin contraseña) y devuelve su código de invitación. */
  async invitar(datos: { email: string; nombre_completo: string; rut: string }): Promise<CodigoInvitacion> {
    const { data } = await api.post("/auth/invitar/", datos);
    return { codigo: data.token_invitacion, expira: data.expira };
  },

  /** Código nuevo para quien aún no activa su cuenta; el anterior deja de servir. */
  async nuevoCodigo(id: string): Promise<CodigoInvitacion> {
    const { data } = await api.post(`/auth/equipo/${id}/invitacion/`);
    return { codigo: data.token_invitacion, expira: data.expira };
  },
};

/**
 * Enlace a «Crear contraseña», SIN el código: si el código fuera en la dirección
 * quedaría guardado en el historial del navegador y en los registros de los
 * servidores por donde pasa. La persona lo escribe en la página.
 */
export function enlaceInvitacion(): string {
  return `${window.location.origin}/crear-contrasena`;
}

/** "14 de noviembre" */
export function fechaVencimiento(expira: string): string {
  return new Date(expira).toLocaleDateString("es-CL", { day: "numeric", month: "long" });
}

/** Texto listo para pegar en WhatsApp o en un correo. */
export function mensajeInvitacion(nombre: string, organizacion: string | null, inv: CodigoInvitacion): string {
  const primerNombre = nombre.trim().split(/\s+/)[0] || nombre;
  return [
    `Hola ${primerNombre}, te invité a EasyLit${organizacion ? ` (${organizacion})` : ""}.`,
    "",
    `1. Entra a este enlace: ${enlaceInvitacion()}`,
    "2. Escribe este código de invitación:",
    inv.codigo,
    "3. Crea tu contraseña y listo.",
    "",
    `El código sirve una sola vez y vence el ${fechaVencimiento(inv.expira)}. No lo compartas con nadie.`,
  ].join("\n");
}
