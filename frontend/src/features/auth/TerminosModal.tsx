/**
 * Ventana con los Términos y condiciones de uso de EasyLit.
 *
 * Se abre desde el enlace azul de "Crear contraseña". El texto resume lo
 * comprometido en el Informe 2 (SLA: responsabilidades, disponibilidad,
 * servicios externos) y las reglas del producto (montos ocultos para la IA,
 * bitácora). Si cambian, actualizar VERSION_TERMINOS y el texto.
 */
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import "./terminos.css";

export const VERSION_TERMINOS = "1.0 · noviembre de 2026";

const SECCIONES: { titulo: string; parrafos: string[] }[] = [
  {
    titulo: "1. Qué es EasyLit",
    parrafos: [
      "EasyLit es una plataforma web que transforma los archivos Excel de licitaciones desde el formato propio de la empresa al formato que exige cada mandante, usando plantillas y apoyo de inteligencia artificial.",
      "Al crear tu contraseña y usar la plataforma, aceptas estos términos.",
    ],
  },
  {
    titulo: "2. Tu cuenta",
    parrafos: [
      "Tu cuenta es personal e intransferible. Se crea solo por invitación de tu gerente y queda asociada a tu organización.",
      "Eres responsable de mantener tu contraseña en reserva. Si crees que alguien más la conoce, cámbiala y avisa a tu gerente.",
    ],
  },
  {
    titulo: "3. Uso de la plataforma",
    parrafos: [
      "Te comprometes a usar EasyLit solo para el trabajo de tu organización, dentro de los márgenes y límites establecidos y apoyándote en el material instructivo disponible.",
      "No debes subir archivos con virus, contenido ajeno a las licitaciones ni información que no tengas derecho a usar.",
    ],
  },
  {
    titulo: "4. Uso de inteligencia artificial",
    parrafos: [
      "EasyLit usa la API de Google Gemini para proponer cómo emparejar los datos del archivo de origen con los campos de la plantilla.",
      "Por defecto, los montos y cantidades nunca se envían a la IA: se reemplazan por «<número oculto>» antes de consultarla.",
      "La IA solo propone. Tú revisas y apruebas el mapeo antes de generar el documento, y eres responsable de verificar el documento final antes de presentarlo en una licitación.",
    ],
  },
  {
    titulo: "5. Tus datos y archivos",
    parrafos: [
      "Para tu cuenta guardamos tu nombre, correo electrónico, RUT y teléfono. Se usan solo para identificarte dentro de EasyLit y en tu organización.",
      "Los archivos que subes y los documentos generados se guardan en Cloudflare R2. El inicio de sesión lo gestiona Firebase (Google) y la información de la plataforma se guarda en una base de datos alojada en Render.",
      "El proveedor se compromete a proteger la confidencialidad e integridad de tus datos y archivos, y a tratarlos conforme a la Ley N° 19.628 sobre protección de la vida privada.",
    ],
  },
  {
    titulo: "6. Registro de actividad",
    parrafos: [
      "Para dar trazabilidad, EasyLit registra en una bitácora quién realizó cada acción (cargar, transformar, generar, eliminar) y cuándo. Este registro lo pueden ver los usuarios autorizados de tu organización.",
    ],
  },
  {
    titulo: "7. Disponibilidad y soporte",
    parrafos: [
      "El servicio está disponible las 24 horas, los 7 días de la semana, salvo mantenciones programadas (sábados de 08:00 a 14:00), que se avisan con anticipación.",
      "El soporte y los tiempos de respuesta dependen del plan contratado por tu organización. Las incidencias se informan por los canales oficiales, con una descripción del problema.",
    ],
  },
  {
    titulo: "8. Cambios a estos términos",
    parrafos: [
      "Estos términos pueden actualizarse. Si hay cambios importantes, se te informará por los canales oficiales.",
    ],
  },
];

interface Props {
  onCerrar: () => void;
  /**
   * Marca la casilla y cierra la ventana (pantalla Crear contraseña). Sin él,
   * la ventana es solo de lectura (por ejemplo, abierta desde el footer).
   */
  onAceptar?: () => void;
  /** Abre la ventana mostrando esa sección (índice en SECCIONES). */
  seccion?: number;
}

/** Índices de SECCIONES, para abrir los términos en una parte concreta. */
export const SECCION_TERMINOS = { inicio: 0, ia: 3, datos: 4, soporte: 6 } as const;

export default function TerminosModal({ onCerrar, onAceptar, seccion }: Props) {
  const cerrarRef = useRef<HTMLButtonElement>(null);
  const cuerpoRef = useRef<HTMLDivElement>(null);

  // Foco en la ventana y Escape para cerrar, como cualquier diálogo.
  useEffect(() => {
    cerrarRef.current?.focus();
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") onCerrar(); };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [onCerrar]);

  // Bajar hasta la sección pedida (solo dentro de la ventana, sin mover la página).
  useEffect(() => {
    // .terminos-cuerpo es position: relative, así offsetTop se mide desde su borde.
    const destino = seccion ? cuerpoRef.current?.children[seccion] : null;
    if (destino && cuerpoRef.current) {
      cuerpoRef.current.scrollTop = (destino as HTMLElement).offsetTop - 12;
    }
  }, [seccion]);

  // Portal a <body>: así la ventana no hereda estilos de donde se abra (por
  // ejemplo, los colores del footer oscuro).
  return createPortal(
    <div className="terminos-overlay" onClick={onCerrar}>
      <div className="terminos-modal" role="dialog" aria-modal="true" aria-labelledby="terminos-titulo"
        onClick={(e) => e.stopPropagation()}>
        <header className="terminos-cabecera">
          <div>
            <h2 id="terminos-titulo">Términos y condiciones de uso</h2>
            <p className="terminos-version">Versión {VERSION_TERMINOS}</p>
          </div>
          <button ref={cerrarRef} type="button" className="terminos-x" onClick={onCerrar} aria-label="Cerrar">
            <i aria-hidden="true" className="ti ti-x" />
          </button>
        </header>

        <div className="terminos-cuerpo" ref={cuerpoRef}>
          {SECCIONES.map((s) => (
            <section key={s.titulo}>
              <h3>{s.titulo}</h3>
              {s.parrafos.map((p) => <p key={p}>{p}</p>)}
            </section>
          ))}
        </div>

        <footer className="terminos-pie">
          {onAceptar ? (
            <>
              <button type="button" className="btn" onClick={onCerrar}>Cerrar</button>
              <button type="button" className="btn btn-primary" onClick={onAceptar}>
                <i aria-hidden="true" className="ti ti-check" /> Acepto los términos
              </button>
            </>
          ) : (
            <button type="button" className="btn btn-primary" onClick={onCerrar}>Cerrar</button>
          )}
        </footer>
      </div>
    </div>,
    document.body,
  );
}
