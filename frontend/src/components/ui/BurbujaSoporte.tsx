/**
 * Burbuja de soporte: una pestaña asomada en el borde derecho de la pantalla.
 * Al pasar el mouse se despliega y muestra «¿Necesitas soporte?»; al hacer
 * clic abre un panel con los canales de contacto.
 *
 * Los canales vienen de variables de entorno (ver lib/soporte.ts). Se muestran
 * solo los que estén definidos.
 */
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/features/auth/AuthContext";
import {
  SOPORTE_CORREO as CORREO, SOPORTE_WHATSAPP as WHATSAPP, enlaceCorreoSoporte, enlaceWhatsappSoporte,
} from "@/lib/soporte";
import "./soporte.css";

export default function BurbujaSoporte() {
  const { usuario } = useAuth();
  const [abierto, setAbierto] = useState(false);
  const cajaRef = useRef<HTMLDivElement>(null);
  const botonRef = useRef<HTMLButtonElement>(null);

  // Cerrar con Escape o con un clic fuera del panel.
  useEffect(() => {
    if (!abierto) return;
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setAbierto(false); botonRef.current?.focus(); }
    };
    const alClic = (e: MouseEvent) => {
      if (cajaRef.current && !cajaRef.current.contains(e.target as Node)) setAbierto(false);
    };
    window.addEventListener("keydown", alTeclear);
    window.addEventListener("mousedown", alClic);
    return () => {
      window.removeEventListener("keydown", alTeclear);
      window.removeEventListener("mousedown", alClic);
    };
  }, [abierto]);

  // Mensaje inicial con lo que sirve para ayudar: quién escribe y desde qué pantalla.
  const quien = usuario
    ? `Soy ${usuario.nombre_completo} (${usuario.email}${usuario.organizacion_nombre ? `, ${usuario.organizacion_nombre}` : ""}).`
    : "";
  const texto = [
    "Hola, necesito ayuda con EasyLit.",
    quien,
    `Pantalla: ${window.location.pathname}`,
    "",
    "Lo que pasó:",
  ].filter((l) => l !== "").join("\n");

  const enlaceCorreo = enlaceCorreoSoporte(texto);
  const enlaceWhatsapp = enlaceWhatsappSoporte(texto);

  return (
    <div className={`soporte ${abierto ? "abierto" : ""}`} ref={cajaRef}>
      {abierto && (
        <div className="soporte-panel" role="dialog" aria-labelledby="soporte-titulo">
          <div className="soporte-panel-cab">
            <h2 id="soporte-titulo">¿Necesitas soporte?</h2>
            <button type="button" className="soporte-x" onClick={() => setAbierto(false)} aria-label="Cerrar">
              <i aria-hidden="true" className="ti ti-x" />
            </button>
          </div>
          <p>Cuéntanos qué pasó y te ayudamos lo antes posible. Si es un error, adjunta una captura de pantalla.</p>

          {WHATSAPP || CORREO ? (
            <div className="soporte-canales">
              {WHATSAPP && (
                <a className="soporte-canal" href={enlaceWhatsapp} target="_blank" rel="noopener noreferrer">
                  <i aria-hidden="true" className="ti ti-brand-whatsapp" />
                  <span><strong>WhatsApp</strong><small>Escríbenos un mensaje</small></span>
                </a>
              )}
              {CORREO && (
                <a className="soporte-canal" href={enlaceCorreo}>
                  <i aria-hidden="true" className="ti ti-mail" />
                  <span><strong>Correo</strong><small>{CORREO}</small></span>
                </a>
              )}
            </div>
          ) : (
            <p className="soporte-sin-canal">
              Aún no hay un canal de soporte configurado. Por ahora, avísale a tu gerente.
            </p>
          )}
        </div>
      )}

      <button
        ref={botonRef}
        type="button"
        className="soporte-pestana"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        aria-label="¿Necesitas soporte?"
      >
        <i aria-hidden="true" className="ti ti-headset" />
        <span className="soporte-texto">¿Necesitas soporte?</span>
      </button>
    </div>
  );
}
