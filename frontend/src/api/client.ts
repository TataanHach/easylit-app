/**
 * Cliente HTTP central.
 *
 * Un solo axios configurado para toda la app: añade el token JWT a cada
 * petición y, si el backend responde 401 por token vencido, intenta refrescarlo
 * una vez de forma transparente antes de rendirse. Los endpoints concretos se
 * conectan en el bloque de autenticación y siguientes.
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

// En dev, el proxy de Vite atiende "/api". En prod, VITE_API_URL apunta a Render.
const baseURL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : "/api";

export const api = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

// Almacenamiento de tokens. Se centraliza aquí para poder cambiarlo luego
// (p. ej. a cookies httpOnly) tocando un solo archivo.
const ACCESS = "easylit_access";
const REFRESH = "easylit_refresh";

export const tokenStore = {
  get access() {
    return localStorage.getItem(ACCESS);
  },
  get refresh() {
    return localStorage.getItem(REFRESH);
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS, access);
    if (refresh) localStorage.setItem(REFRESH, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  },
};

// Añade el token a cada petición saliente.
api.interceptors.request.use((cfg: InternalAxiosRequestConfig) => {
  const token = tokenStore.access;
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// Refresco transparente ante un 401 por token vencido.
let refreshing: Promise<string> | null = null;

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !original._retry && tokenStore.refresh) {
      original._retry = true;
      try {
        refreshing ??= axios
          .post(`${baseURL}/auth/refresh/`, { refresh: tokenStore.refresh })
          .then((r) => {
            tokenStore.set(r.data.access);
            return r.data.access as string;
          })
          .finally(() => {
            refreshing = null;
          });

        const nuevo = await refreshing;
        original.headers.Authorization = `Bearer ${nuevo}`;
        return api(original);
      } catch {
        tokenStore.clear();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);
