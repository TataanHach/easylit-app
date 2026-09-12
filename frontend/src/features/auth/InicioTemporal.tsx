/**
 * Página provisional tras el login. Confirma que la sesión funciona mostrando
 * los datos reales del usuario que devolvió el backend. Se reemplaza por el
 * dashboard/historial en el siguiente bloque de frontend.
 */
import { useAuth } from "./AuthContext";

export default function InicioTemporal() {
  const { usuario, logout } = useAuth();

  return (
    <div style={{ maxWidth: 560, margin: "60px auto", padding: 24 }}>
      <div style={{
        background: "var(--surface)", border: "1px solid var(--line)",
        borderRadius: "var(--r-lg)", padding: 28,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
          <span style={{
            width: 36, height: 36, borderRadius: "var(--r-md)",
            background: "var(--dest-50)", display: "grid", placeItems: "center",
          }}>
            <i className="ti ti-circle-check" style={{ color: "var(--ok-600)", fontSize: 20 }} />
          </span>
          <h1 style={{ fontSize: 20 }}>¡Sesión iniciada!</h1>
        </div>
        <p style={{ color: "var(--text-2)", marginBottom: 20 }}>
          El login funciona y está conectado a tu backend. Estos datos vienen de la API:
        </p>
        <div style={{ display: "grid", gap: 10, fontSize: 14 }}>
          <Dato etiqueta="Nombre" valor={usuario?.nombre_completo} />
          <Dato etiqueta="Correo" valor={usuario?.email} />
          <Dato etiqueta="Rol" valor={usuario?.rol} />
          <Dato etiqueta="Organización" valor={usuario?.organizacion_nombre ?? "—"} />
        </div>
        <button onClick={logout} style={{
          marginTop: 24, padding: "9px 16px", borderRadius: "var(--r-md)",
          border: "1px solid var(--line-strong)", background: "var(--surface)",
          cursor: "pointer", fontSize: 13, fontWeight: 600,
        }}>
          <i className="ti ti-logout" /> Cerrar sesión
        </button>
      </div>
      <p style={{ textAlign: "center", color: "var(--text-3)", fontSize: 12, marginTop: 16 }}>
        Pantalla provisional · el historial y el wizard llegan en el próximo bloque
      </p>
    </div>
  );
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor?: string | null }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between",
      padding: "10px 14px", background: "var(--surface-2)",
      borderRadius: "var(--r-md)", border: "1px solid var(--line-soft)",
    }}>
      <span style={{ color: "var(--text-2)" }}>{etiqueta}</span>
      <strong>{valor}</strong>
    </div>
  );
}
