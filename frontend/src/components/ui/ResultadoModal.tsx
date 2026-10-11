/**
 * Ventana emergente con el resultado de una operación larga (revisar una
 * plantilla, procesar una transformación, generar el documento).
 *
 *   ✓ exito       todo salió bien: resumen con las cifras.
 *   ⚠ advertencia salió, pero hay cosas que revisar: la lista agrupada de qué
 *                 y dónde, con el motivo de cada una.
 *   ✗ error       no se pudo: qué pasó y qué hacer.
 *
 * A diferencia de los avisos de la esquina, bloquea la pantalla hasta que el
 * usuario la cierra, para que el resultado no pase desapercibido.
 */
import { useEffect, useRef } from "react";
import "./resultado-modal.css";

export type EstadoResultado = "exito" | "advertencia" | "error";

export interface Resultado {
  estado: EstadoResultado;
  titulo: string;
  mensaje: string;
  /** Cifras del resumen, ej. [{ etiqueta: "Campos", valor: 12 }]. */
  cifras?: { etiqueta: string; valor: string | number }[];
  /** Problemas agrupados (por hoja, por tipo…): título del grupo y sus ítems. */
  grupos?: { titulo: string; items: string[] }[];
}

interface Props {
  resultado: Resultado;
  onAceptar: () => void;
  /** Botón secundario opcional, ej. "Corregir campos". */
  secundario?: { texto: string; onClick: () => void };
}

const ICONO: Record<EstadoResultado, string> = {
  exito: "ti ti-circle-check",
  advertencia: "ti ti-alert-triangle",
  error: "ti ti-circle-x",
};

export default function ResultadoModal({ resultado, onAceptar, secundario }: Props) {
  const { estado, titulo, mensaje, cifras, grupos } = resultado;
  const aceptarRef = useRef<HTMLButtonElement>(null);

  // Foco en "Aceptar" y Escape para cerrar, como cualquier diálogo.
  useEffect(() => {
    aceptarRef.current?.focus();
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") onAceptar(); };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [onAceptar]);

  return (
    <div className="resultado-overlay">
      <div className={`resultado-modal resultado-${estado}`} role="alertdialog" aria-modal="true"
        aria-labelledby="resultado-titulo" aria-describedby="resultado-mensaje">
        <div className="resultado-icono"><i className={ICONO[estado]} /></div>
        <h2 id="resultado-titulo">{titulo}</h2>
        <p id="resultado-mensaje" className="resultado-mensaje">{mensaje}</p>

        {cifras && cifras.length > 0 && (
          <div className="resultado-cifras">
            {cifras.map((c) => (
              <div key={c.etiqueta} className="resultado-cifra">
                <span className="resultado-cifra-valor">{c.valor}</span>
                <span className="resultado-cifra-etiqueta">{c.etiqueta}</span>
              </div>
            ))}
          </div>
        )}

        {grupos && grupos.length > 0 && (
          <div className="resultado-grupos">
            {grupos.map((g) => (
              <div key={g.titulo} className="resultado-grupo">
                <p className="resultado-grupo-titulo">{g.titulo}</p>
                <ul>{g.items.map((item, i) => <li key={i}>{item}</li>)}</ul>
              </div>
            ))}
          </div>
        )}

        <div className="resultado-botones">
          {secundario && <button className="btn" onClick={secundario.onClick}>{secundario.texto}</button>}
          <button ref={aceptarRef} className="btn btn-primary" onClick={onAceptar}>Aceptar</button>
        </div>
      </div>
    </div>
  );
}
