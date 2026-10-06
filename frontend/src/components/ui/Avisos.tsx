/**
 * Avisos flotantes (toasts) para toda la app.
 *
 * Reemplazan a los `alert()`: se ven en la esquina, dicen qué pasó y qué hacer,
 * y no bloquean la pantalla. Los de éxito se cierran solos; los de error se
 * quedan hasta que el usuario los cierra, para que no pasen desapercibidos.
 *
 *   const avisos = useAvisos();
 *   avisos.exito("Transformación realizada con éxito");
 *   avisos.error(describirError(e, "eliminar la transformación"));
 */
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { MensajeError } from "@/lib/errores";
import "./avisos.css";

type Tipo = "exito" | "error" | "info" | "advertencia";

interface Aviso {
  id: number;
  tipo: Tipo;
  titulo: string;
  detalle?: string;
}

interface AvisosApi {
  exito: (titulo: string, detalle?: string) => void;
  error: (msg: MensajeError | string, detalle?: string) => void;
  info: (titulo: string, detalle?: string) => void;
  advertencia: (titulo: string, detalle?: string) => void;
}

const AvisosContext = createContext<AvisosApi | null>(null);

const ICONOS: Record<Tipo, string> = {
  exito: "ti ti-circle-check",
  error: "ti ti-alert-circle",
  info: "ti ti-info-circle",
  advertencia: "ti ti-alert-triangle",
};

// Tiempo en pantalla antes de cerrarse solo. Los errores no se cierran solos.
const DURACION: Record<Tipo, number | null> = { exito: 5000, info: 7000, advertencia: 10000, error: null };

let siguienteId = 1;

export function AvisosProvider({ children }: { children: ReactNode }) {
  const [avisos, setAvisos] = useState<Aviso[]>([]);

  const cerrar = useCallback((id: number) => {
    setAvisos((lista) => lista.filter((a) => a.id !== id));
  }, []);

  const mostrar = useCallback((tipo: Tipo, titulo: string, detalle?: string) => {
    const id = siguienteId++;
    // Máximo 4 a la vez: los más viejos se van.
    setAvisos((lista) => [...lista.slice(-3), { id, tipo, titulo, detalle }]);
    const ms = DURACION[tipo];
    if (ms) setTimeout(() => cerrar(id), ms);
  }, [cerrar]);

  const api = useMemo<AvisosApi>(() => ({
    exito: (titulo, detalle) => mostrar("exito", titulo, detalle),
    info: (titulo, detalle) => mostrar("info", titulo, detalle),
    advertencia: (titulo, detalle) => mostrar("advertencia", titulo, detalle),
    error: (msg, detalle) =>
      typeof msg === "string" ? mostrar("error", msg, detalle) : mostrar("error", msg.titulo, msg.detalle),
  }), [mostrar]);

  return (
    <AvisosContext.Provider value={api}>
      {children}
      <div className="avisos" aria-live="polite">
        {avisos.map((a) => (
          <div key={a.id} className={`aviso aviso-${a.tipo}`} role={a.tipo === "error" ? "alert" : "status"}>
            <i className={`aviso-icono ${ICONOS[a.tipo]}`} />
            <div className="aviso-texto">
              <p className="aviso-titulo">{a.titulo}</p>
              {a.detalle && <p className="aviso-detalle">{a.detalle}</p>}
            </div>
            <button className="aviso-cerrar" onClick={() => cerrar(a.id)} title="Cerrar" aria-label="Cerrar aviso">
              <i className="ti ti-x" />
            </button>
          </div>
        ))}
      </div>
    </AvisosContext.Provider>
  );
}

export function useAvisos(): AvisosApi {
  const ctx = useContext(AvisosContext);
  if (!ctx) throw new Error("useAvisos debe usarse dentro de <AvisosProvider>.");
  return ctx;
}
