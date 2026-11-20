/**
 * Footer de la app: datos de EasyLit, información legal, accesos a las
 * secciones y contacto. Va al final de cada pantalla interna (Layout).
 */
import { useState } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";
import TerminosModal, { SECCION_TERMINOS } from "@/features/auth/TerminosModal";
import { SOPORTE_CORREO, enlaceCorreoSoporte } from "@/lib/soporte";
import logo from "@/assets/logo.png";
import "./footer.css";

export default function Footer() {
  const { usuario } = useAuth();
  // undefined = cerrada; un número = abierta en esa sección.
  const [terminos, setTerminos] = useState<number | undefined>(undefined);

  return (
    <footer className="pie">
      <div className="pie-contenedor">
        <div className="pie-columnas">
          <div className="pie-col">
            <h2>EasyLit</h2>
            <img className="pie-logo" src={logo} alt="EasyLit" width={600} height={162} />
            <p>Tú defines el formato, EasyLit lo transforma para ti.</p>
          </div>

          <div className="pie-col">
            <h2>Información</h2>
            <button type="button" onClick={() => setTerminos(SECCION_TERMINOS.inicio)}>Términos y condiciones</button>
            <button type="button" onClick={() => setTerminos(SECCION_TERMINOS.datos)}>Protección de datos</button>
            <button type="button" onClick={() => setTerminos(SECCION_TERMINOS.ia)}>Uso de inteligencia artificial</button>
            <button type="button" onClick={() => setTerminos(SECCION_TERMINOS.soporte)}>Disponibilidad del servicio</button>
          </div>

          <nav className="pie-col" aria-label="Secciones">
            <h2>Secciones</h2>
            <NavLink to="/plantillas">Plantillas</NavLink>
            <NavLink to="/transformar">Transformar</NavLink>
            <NavLink to="/historial">Historial</NavLink>
            {usuario?.rol === "GERENTE" && <NavLink to="/equipo">Equipo</NavLink>}
          </nav>

          <div className="pie-col">
            <h2>Contacto</h2>
            {SOPORTE_CORREO ? (
              <>
                <p>Contáctanos al correo:</p>
                <a className="pie-dato" href={enlaceCorreoSoporte()}>
                  <i aria-hidden="true" className="ti ti-mail" /> {SOPORTE_CORREO}
                </a>
              </>
            ) : (
              <span className="pie-dato">
                <i aria-hidden="true" className="ti ti-headset" /> Usa el botón «¿Necesitas soporte?»
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="pie-base">
        © {new Date().getFullYear()} EasyLit | Todos los derechos reservados · Concepción, Chile · v2.5 Beta
      </div>

      {terminos !== undefined && <TerminosModal seccion={terminos} onCerrar={() => setTerminos(undefined)} />}
    </footer>
  );
}
