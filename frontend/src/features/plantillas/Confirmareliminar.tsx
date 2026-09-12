/** Modal de confirmación para eliminar una plantilla. */
import { useState } from "react";
import { plantillaService } from "./plantillaService";
import type { Plantilla } from "@/types";

interface Props { plantilla: Plantilla; onCerrar: () => void; onEliminado: () => void; }

export default function ConfirmarEliminar({ plantilla, onCerrar, onEliminado }: Props) {
  const [eliminando, setEliminando] = useState(false);
  const [error, setError] = useState("");

  async function eliminar() {
    setEliminando(true); setError("");
    try {
      await plantillaService.eliminar(plantilla.id);
      onEliminado();
    } catch {
      setError("No se pudo eliminar. Puede que esté en uso por transformaciones.");
      setEliminando(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onCerrar}>
      <div className="modal" style={{ maxWidth: 400 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>Eliminar plantilla</h2>
          <button className="modal-close" onClick={onCerrar}><i className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          {error && <div className="modal-error">{error}</div>}
          <p className="confirm-text">
            ¿Seguro que quieres eliminar <strong>{plantilla.nombre}</strong>? Esta acción no se puede deshacer.
          </p>
        </div>
        <div className="modal-foot">
          <button className="btn" onClick={onCerrar}>Cancelar</button>
          <button className="btn" style={{ background: "var(--danger-500)", color: "#fff", borderColor: "var(--danger-500)", fontWeight: 600 }}
            onClick={eliminar} disabled={eliminando}>
            {eliminando ? "Eliminando…" : "Sí, eliminar"}
          </button>
        </div>
      </div>
    </div>
  );
}