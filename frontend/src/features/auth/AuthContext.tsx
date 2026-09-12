/**
 * Contexto de autenticación.
 *
 * Mantiene el usuario logueado disponible en toda la app sin pasarlo por props.
 * Al arrancar, si hay un token guardado, intenta restaurar la sesión pidiendo el
 * perfil; así el usuario sigue dentro tras recargar la página.
 */
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { tokenStore } from "@/api/client";
import type { Usuario } from "@/types";
import { authService } from "./authService";

interface AuthContextValue {
  usuario: Usuario | null;
  cargando: boolean;
  login: (email: string, password: string) => Promise<Usuario>;
  crearContrasena: (p: {
    token: string;
    password: string;
    password2: string;
    rut?: string;
    telefono?: string;
  }) => Promise<Usuario>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);

  // Al montar: si hay token, restaurar la sesión.
  useEffect(() => {
    if (!tokenStore.access) {
      setCargando(false);
      return;
    }
    authService
      .perfil()
      .then(setUsuario)
      .catch(() => tokenStore.clear())
      .finally(() => setCargando(false));
  }, []);

  const login = async (email: string, password: string) => {
    const u = await authService.login(email, password);
    setUsuario(u);
    return u;
  };

  const crearContrasena: AuthContextValue["crearContrasena"] = async (p) => {
    const u = await authService.crearContrasena(p);
    setUsuario(u);
    return u;
  };

  const logout = () => {
    authService.logout();
    setUsuario(null);
  };

  return (
    <AuthContext.Provider value={{ usuario, cargando, login, crearContrasena, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
