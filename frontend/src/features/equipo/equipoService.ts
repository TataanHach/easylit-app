/**
 * Servicio del equipo: lo usa el gerente para ver a su gente e invitar
 * trabajadores. EasyLit no envía correos: el gerente copia el mensaje con el
 * código y se lo hace llegar al trabajador (WhatsApp, correo, etc.).
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
  /** Solo viene si el estado es PENDIENTE. */
  codigo: string | null;
  expira: string | null;
}

export interface CodigoInvitacion {
  codigo: string;
  expira: string;
}

export const equipoService = {
  async listar(): Promise<MiembroEquipo[]> {
    const { data } = await api.get<MiembroEquipo[]>("/auth/equipo/");
    return data;
  },

  /** Crea al trabajador (sin contraseña) y devuelve su código de invitación. */
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

/** Enlace que abre «Crear contraseña» con el código ya puesto. */
export function enlaceInvitacion(codigo: string): string {
  return `${window.location.origin}/crear-contrasena?codigo=${encodeURIComponent(codigo)}`;
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
    `1. Entra a este enlace: ${enlaceInvitacion(inv.codigo)}`,
    "2. Crea tu contraseña. Si te pide un código de invitación, usa este:",
    inv.codigo,
    "",
    `El código sirve una sola vez y vence el ${fechaVencimiento(inv.expira)}.`,
  ].join("\n");
}
