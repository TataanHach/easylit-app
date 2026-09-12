/**
 * Servicio de autenticación.
 *
 * Cada función corresponde a un endpoint del backend (bloque 2). Centralizar las
 * llamadas aquí evita esparcir URLs por los componentes: si una ruta cambia, se
 * toca un solo lugar.
 */
import { api, tokenStore } from "@/api/client";
import type { Usuario } from "@/types";

interface LoginResp {
  access: string;
  refresh: string;
  usuario: Usuario;
}

interface EstadoCorreoResp {
  existe: boolean;
  necesita_contrasena: boolean;
}

export const authService = {
  /** Paso previo: ¿el correo existe y ya tiene contraseña? */
  async estadoCorreo(email: string): Promise<EstadoCorreoResp> {
    const { data } = await api.post("/auth/estado-correo/", { email });
    return data;
  },

  /** Login con correo y contraseña. Guarda los tokens y devuelve el usuario. */
  async login(email: string, password: string): Promise<Usuario> {
    const { data } = await api.post<LoginResp>("/auth/login/", { email, password });
    tokenStore.set(data.access, data.refresh);
    return data.usuario;
  },

  /** Primer ingreso: crea la contraseña con el token de invitación. */
  async crearContrasena(payload: {
    token: string;
    password: string;
    password2: string;
    rut?: string;
    telefono?: string;
  }): Promise<Usuario> {
    const { data } = await api.post<LoginResp>("/auth/crear-contrasena/", payload);
    tokenStore.set(data.access, data.refresh);
    return data.usuario;
  },

  /** Datos del usuario autenticado (para restaurar sesión al recargar). */
  async perfil(): Promise<Usuario> {
    const { data } = await api.get<Usuario>("/auth/perfil/");
    return data;
  },

  /** Cierra la sesión borrando los tokens. */
  logout() {
    tokenStore.clear();
  },
};
