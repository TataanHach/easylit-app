/**
 * Ventana para confirmar una acción que no se puede deshacer (ej. eliminar).
 *
 * Usa el mismo estilo y la misma animación que ResultadoModal (ícono ⚠), con
 * dos botones: "Cancelar" (con el foco, para que Enter no borre por error) y
 * el de confirmar. Solo se cierra con sus botones o con Escape (= cancelar).
 *
 * Si `onConfirmar` devuelve una promesa (ej. llamar al servidor), muestra
 * "Eliminando…" mientras espera y, si falla, deja la ventana abierta con el
 * error explicado. Si sale bien, quien la abrió es quien la cierra.
 *
 * Se dibuja en un portal (directo en <body>): así se puede abrir desde una
 * fila de tabla sin meter un <div> dentro de un <tr>.
 */
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { describirError } from "@/lib/errores";
import "./resultado-modal.css";

interface Props {
  titulo: string;
  mensaje: string;
  /** Texto del botón de confirmar, ej. "Sí, eliminar". */
  confirmar: string;
  /** Texto mientras se procesa, ej. "Eliminando…". */
  procesando?: string;
  /** Completa "No se pudo …" si falla, ej. "eliminar la plantilla". */
  accion?: string;
  onConfirmar: () => void | Promise<void>;
  onCancelar: () => void;
}

export default function ConfirmarModal({
  titulo, mensaje, confirmar, procesando = "Procesando…", accion = "completar la acción",
  onConfirmar, onCancelar,
}: Props) {
  const cancelarRef = useRef<HTMLButtonElement>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<{ titulo: string; detalle: string } | null>(null);

  useEffect(() => {
    cancelarRef.current?.focus();
  }, []);

  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape" && !ocupado) onCancelar(); };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [onCancelar, ocupado]);

  async function alConfirmar() {
    setOcupado(true);
    setError(null);
    try {
      await onConfirmar();
    } catch (e) {
      setError(describirError(e, accion));
      setOcupado(false);
    }
  }

  return createPortal(
    <div className="resultado-overlay">
      <div className={`resultado-modal ${error ? "resultado-error" : "resultado-advertencia"}`}
        role="alertdialog" aria-modal="true" aria-labelledby="confirmar-titulo" aria-describedby="confirmar-mensaje">
        {/* key: si aparece un error, el ícono cambia a ✗ y su animación se repite. */}
        <div className="resultado-icono" key={error ? "error" : "aviso"}>
          <svg viewBox="0 0 52 52" aria-hidden="true" className="resultado-svg">
            {error ? (
              <>
                <circle className="trazo contorno" pathLength={1} cx="26" cy="26" r="22" />
                <path className="trazo marca" pathLength={1} d="M18.5 18.5 L33.5 33.5 M33.5 18.5 L18.5 33.5" />
              </>
            ) : (
              <>
                <path className="trazo contorno" pathLength={1} d="M26 6 L48 45 H4 Z" />
                <path className="trazo marca" pathLength={1} d="M26 20 V32" />
                <circle className="punto" cx="26" cy="38.5" r="1.8" />
              </>
            )}
          </svg>
        </div>
        <h2 id="confirmar-titulo">{error ? error.titulo : titulo}</h2>
        <p id="confirmar-mensaje" className="resultado-mensaje">{error ? error.detalle : mensaje}</p>
        <div className="resultado-botones">
          <button ref={cancelarRef} className="btn" onClick={onCancelar} disabled={ocupado}>
            {error ? "Cerrar" : "Cancelar"}
          </button>
          {!error && (
            <button className="btn btn-peligro" onClick={alConfirmar} disabled={ocupado}>
              {ocupado ? <><i className="ti ti-loader-2" /> {procesando}</> : confirmar}
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
