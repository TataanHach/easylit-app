/**
 * Layout de la aplicación.
 *
 * Marco compartido por todas las pantallas internas: sidebar con navegación,
 * topbar, y un <Outlet> donde React Router inserta la pantalla activa. El menú
 * de configuración solo aparece para gerentes y superadmin.
 */
import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";
import "./layout.css";

export default function Layout() {
  const { usuario, logout } = useAuth();
  const navigate = useNavigate();
  const [navAbierto, setNavAbierto] = useState(false);
  const cerrarNav = () => setNavAbierto(false);

  // Con el menú abierto (pantalla angosta), Escape lo cierra.
  useEffect(() => {
    if (!navAbierto) return;
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") setNavAbierto(false); };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [navAbierto]);

  function cerrarSesion() {
    logout();
    navigate("/login");
  }

  // Iniciales para el avatar.
  const iniciales = (usuario?.nombre_completo ?? "")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const puedeConfig =
    usuario?.rol === "GERENTE" || usuario?.rol === "SUPERADMIN";

  return (
    <div className={`app-shell ${navAbierto ? "nav-open" : ""}`}>
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon"><i className="ti ti-file-invoice" /></div>
          <div>
            <div className="logo-text">EasyLit</div>
            <div className="logo-sub">v1.0 · Beta</div>
          </div>
          {/* Solo en pantalla angosta: el menú tapa el botón ☰, así que lleva su propio cierre. */}
          <button className="nav-cerrar" onClick={cerrarNav} aria-label="Cerrar menú">
            <i className="ti ti-x" />
          </button>
        </div>

        {/* Elegir una sección también cierra el menú (en pantalla ancha no hace nada). */}
        <nav className="sidebar-nav" onClick={(e) => { if ((e.target as HTMLElement).closest("a")) cerrarNav(); }}>
          <p className="nav-section">Principal</p>
          <NavLink to="/transformar" className={({ isActive }) => `nav-item ${isActive ? "activo" : ""}`}>
            <i className="ti ti-arrows-transfer-up" /> Transformar
          </NavLink>
          <NavLink to="/historial" className={({ isActive }) => `nav-item ${isActive ? "activo" : ""}`}>
            <i className="ti ti-clock-hour-4" /> Historial
          </NavLink>
          <NavLink to="/plantillas" className={({ isActive }) => `nav-item ${isActive ? "activo" : ""}`}>
            <i className="ti ti-template" /> Plantillas
          </NavLink>

          {puedeConfig && (
            <>
              <p className="nav-section">Configuración</p>
              <NavLink to="/equipo" className={({ isActive }) => `nav-item ${isActive ? "activo" : ""}`}>
                <i className="ti ti-users" /> Equipo
              </NavLink>
            </>
          )}
        </nav>

        <a className="sidebar-bottom" onClick={cerrarSesion} style={{ cursor: "pointer" }}>
          <div className="avatar">{iniciales}</div>
          <div className="avatar-info">
            <p>{usuario?.nombre_completo}</p>
            <span>{rolLegible(usuario?.rol)}</span>
          </div>
          <i className="ti ti-logout logout-icon" title="Cerrar sesión" />
        </a>
      </aside>

      {/* Fondo oscuro detrás del menú abierto: un clic afuera lo cierra. */}
      {navAbierto && <div className="nav-fondo" onClick={cerrarNav} />}

      <div className="main-col">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button className="nav-toggle" onClick={() => setNavAbierto(!navAbierto)} aria-label="Abrir menú" aria-expanded={navAbierto}>
              <i className="ti ti-menu-2" />
            </button>
            <span className="topbar-title">{usuario?.organizacion_nombre ?? "EasyLit"}</span>
          </div>
          <div className="topbar-right">
            <NavLink to="/transformar" className="btn btn-primary">
              <i className="ti ti-plus" /> Nueva transformación
            </NavLink>
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function rolLegible(rol?: string) {
  switch (rol) {
    case "SUPERADMIN": return "Superadministrador";
    case "GERENTE": return "Gerente";
    case "TRABAJADOR": return "Trabajador";
    default: return "";
  }
}
