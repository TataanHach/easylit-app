/**
 * Envuelve las rutas que requieren sesión. Si no hay usuario, redirige a login.
 * Mientras se restaura la sesión (al recargar), muestra un cargando breve.
 */
import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./AuthContext";

export default function RutaProtegida({ children }: { children: ReactNode }) {
  const { usuario, cargando } = useAuth();

  if (cargando) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: "100dvh", color: "var(--text-3)" }}>
        Cargando…
      </div>
    );
  }
  if (!usuario) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
