/**
 * Modal para crear o editar una plantilla.
 *
 * En modo crear: pide nombre, mandante, formato y archivo.
 * En modo editar: permite cambiar nombre/mandante/sector (no el archivo, para
 * no invalidar transformaciones que ya lo usan).
 */
import { FormEvent, useState } from "react";
import { plantillaService } from "./plantillaService";
import type { Plantilla } from "@/types";

interface Props {
  plantilla?: Plantilla | null; // si viene, es edición
  onCerrar: () => void;
  onGuardado: () => void;
}

export default function PlantillaModal({ plantilla, onCerrar, onGuardado }: Props) {
  const esEdicion = !!plantilla;
  const [nombre, setNombre] = useState(plantilla?.nombre ?? "");
  const [mandante, setMandante] = useState(plantilla?.mandante ?? "");
  const [sector, setSector] = useState(plantilla?.sector ?? "");
  const [formato, setFormato] = useState<string>(plantilla?.formato ?? "XLSX");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!nombre.trim()) { setError("El nombre es obligatorio."); return; }
    if (!esEdicion && !archivo) { setError("Sube el archivo del formato."); return; }
    setGuardando(true);
    try {
      if (esEdicion) {
        await plantillaService.editar(plantilla!.id, { nombre, mandante, sector });
      } else {
        await plantillaService.crear({ nombre, mandante, sector, formato, archivo: archivo! });
      }
      onGuardado();
    } catch {
      setError("No se pudo guardar. Revisa los datos e intenta de nuevo.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{esEdicion ? "Editar plantilla" : "Nueva plantilla"}</h2>
          <button className="modal-close" onClick={onCerrar}><i className="ti ti-x" /></button>
        </div>
        <form onSubmit={guardar}>
          <div className="modal-body">
            {error && <div className="modal-error">{error}</div>}

            <div className="mfield">
              <label>Nombre *</label>
              <input value={nombre} onChange={(e) => setNombre(e.target.value)}
                placeholder="Ej. Formulario Identificación MINEDUC" autoFocus />
            </div>
            <div className="mfield">
              <label>Mandante</label>
              <input value={mandante} onChange={(e) => setMandante(e.target.value)}
                placeholder="Ej. MINEDUC, Codelco…" />
            </div>
            <div className="mfield">
              <label>Sector</label>
              <input value={sector} onChange={(e) => setSector(e.target.value)}
                placeholder="Ej. Educación, Minería…" />
            </div>

            {!esEdicion && (
              <>
                <div className="mfield">
                  <label>Formato</label>
                  <select value={formato} onChange={(e) => setFormato(e.target.value)}>
                    <option value="XLSX">Excel (XLSX)</option>
                    <option value="CSV">CSV</option>
                  </select>
                </div>
                <div className="mfield">
                  <label>Archivo del formato *</label>
                  <label className={`file-drop ${archivo ? "tiene" : ""}`}>
                    <input type="file" accept=".xlsx,.xls,.csv" style={{ display: "none" }}
                      onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
                    {archivo ? <><i className="ti ti-file-check" /> {archivo.name}</>
                            : <><i className="ti ti-upload" /> Haz clic para subir el Excel</>}
                  </label>
                </div>
              </>
            )}

            {esEdicion && (
              <p style={{ fontSize: "var(--fs-sm)", color: "var(--text-3)" }}>
                Para cambiar el archivo o los campos, hazlo desde el panel de administración.
              </p>
            )}
          </div>
          <div className="modal-foot">
            <button type="button" className="btn" onClick={onCerrar}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={guardando}>
              {guardando ? "Guardando…" : esEdicion ? "Guardar cambios" : "Crear plantilla"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}