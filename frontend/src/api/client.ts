/**
 * Cliente HTTP central.
 *
 * Un solo axios configurado para toda la app: añade el token JWT a cada
 * petición y, si el backend responde 401 por token vencido, intenta refrescarlo
 * una vez de forma transparente antes de rendirse. Los endpoints concretos se
 * conectan en el bloque de autenticación y siguientes.
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { auth, firebaseActivo } from "@/lib/firebase";

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
//
// Va en sessionStorage, no en localStorage: al cerrar la pestaña o el navegador
// los tokens se borran y hay que volver a iniciar sesión. Así nadie entra con la
// sesión de otro por abrir el navegador después.
const ACCESS = "easylit_access";
const REFRESH = "easylit_refresh";

// Versiones anteriores guardaban los tokens en localStorage: se borran para que
// esas sesiones "recordadas" no sigan vivas.
localStorage.removeItem(ACCESS);
localStorage.removeItem(REFRESH);

export const tokenStore = {
  get access() {
    return sessionStorage.getItem(ACCESS);
  },
  get refresh() {
    return sessionStorage.getItem(REFRESH);
  },
  set(access: string, refresh?: string) {
    sessionStorage.setItem(ACCESS, access);
    if (refresh) sessionStorage.setItem(REFRESH, refresh);
  },
  clear() {
    sessionStorage.removeItem(ACCESS);
    sessionStorage.removeItem(REFRESH);
  },
};

// Añade el token a cada petición saliente.
api.interceptors.request.use(async (cfg: InternalAxiosRequestConfig) => {
  // Con Firebase, su SDK entrega un token vigente (lo renueva solo cada hora).
  const token = firebaseActivo
    ? await auth?.currentUser?.getIdToken()
    : tokenStore.access;
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// Refresco transparente ante un 401 por token vencido.
let refreshing: Promise<string> | null = null;

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // (Con Firebase no aplica: su SDK ya renueva el token antes de cada petición.)
    if (!firebaseActivo && error.response?.status === 401 && !original._retry && tokenStore.refresh) {
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
