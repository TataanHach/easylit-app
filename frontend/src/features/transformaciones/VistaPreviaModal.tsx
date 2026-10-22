/**
 * Vista previa de solo lectura de una transformación ya generada.
 *
 * Se abre desde el historial: muestra, hoja por hoja, los campos y tablas con el
 * valor que quedó en el documento, y permite descargarlo sin ir al mapeo.
 */
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { transformacionService } from "@/features/historial/historialService";
import { describirError } from "@/lib/errores";
import { TablaItemizado } from "./MapeoPage";
import "@/features/plantillas/plantillas.css";
import "./mapeo.css";

export default function VistaPreviaModal({ id, nombre, onDescargar, descargando, onCerrar }: {
  id: string; nombre: string;
  onDescargar: () => void; descargando: boolean; onCerrar: () => void;
}) {
  const [hojaActiva, setHojaActiva] = useState(0);
  const { data: preview, isLoading, error } = useQuery({
    queryKey: ["vistaPrevia", id],
    queryFn: () => transformacionService.vistaPrevia(id),
  });

  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") onCerrar(); };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [onCerrar]);

  const hojas = preview?.hojas ?? [];
  const hoja = hojas[hojaActiva];
  // Los avisos traen la instrucción para la pantalla de mapeo; aquí ya no hay mapeo que editar.
  const pendientes: string[] = (preview?.avisos ?? []).map((a: string) =>
    a.replace(/\s*Asígnale uno en el mapeo de abajo\.?\s*$/, ""));

  return createPortal(
    <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) onCerrar(); }}>
      <div className="modal vista-previa-modal" role="dialog" aria-modal="true" aria-labelledby="vista-previa-titulo">
        <div className="modal-head">
          <div style={{ minWidth: 0 }}>
            <h2 id="vista-previa-titulo">Vista previa del documento</h2>
            <p className="vista-previa-sub" title={nombre}>{nombre}</p>
          </div>
          <button className="modal-close" onClick={onCerrar} aria-label="Cerrar">
            <i aria-hidden="true" className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">
          {isLoading && (
            <p className="vista-previa-estado"><i aria-hidden="true" className="ti ti-loader-2" /> Cargando vista previa…</p>
          )}
          {error && (
            <div className="banda banda-error">
              <i aria-hidden="true" className="ti ti-alert-circle" />
              <div><strong>No se pudo cargar la vista previa</strong>{describirError(error, "cargar la vista previa").detalle}</div>
            </div>
          )}

          {pendientes.length > 0 && (
            <div className="pendientes-caja" role="status">
              <p className="pendientes-titulo">
                <i aria-hidden="true" className="ti ti-alert-triangle" />
                {pendientes.length === 1 ? "1 dato quedó sin llenar" : `${pendientes.length} datos quedaron sin llenar`} en el documento
              </p>
              <ul>{pendientes.map((a, i) => <li key={i}>{a}</li>)}</ul>
            </div>
          )}

          {hoja && (
            <div className="mapeo-panel" style={{ marginBottom: 0 }}>
              <div className="preview-nav">
                <button className="preview-flecha" disabled={hojaActiva === 0} aria-label="Hoja anterior"
                  onClick={() => setHojaActiva((h) => Math.max(0, h - 1))}>
                  <i aria-hidden="true" className="ti ti-chevron-left" />
                </button>
                <div className="preview-titulo">
                  <span className="preview-hoja-nombre">{hoja.nombre}</span>
                  <span className="preview-hoja-contador">
                    Hoja {hojaActiva + 1} de {hojas.length}
                    {hoja.tipo === "itemizado" && <span className="preview-badge-item">tabla</span>}
                  </span>
                </div>
                <button className="preview-flecha" disabled={hojaActiva >= hojas.length - 1} aria-label="Hoja siguiente"
                  onClick={() => setHojaActiva((h) => Math.min(hojas.length - 1, h + 1))}>
                  <i aria-hidden="true" className="ti ti-chevron-right" />
                </button>
              </div>

              {hoja.campos?.length > 0 && (
                <table className="preview-tabla">
                  <thead><tr><th>Campo</th><th>Valor en el documento</th></tr></thead>
                  <tbody>
                    {hoja.campos.map((f: any, i: number) => (
                      <tr key={i}>
                        <td>{f.campo}</td>
                        <td style={{ fontWeight: f.valor_final ? 500 : 400,
                                     color: f.valor_final ? "var(--text)" : "var(--text-3)" }}>
                          {f.valor_final || "(vacío)"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {hoja.tipo === "itemizado" && <TablaItemizado key={hoja.nombre} hoja={hoja} />}
            </div>
          )}
        </div>

        <div className="modal-foot">
          <button className="btn" onClick={onCerrar}>Cerrar</button>
          <button className="btn btn-primary" onClick={onDescargar} disabled={descargando}>
            {descargando
              ? <><i aria-hidden="true" className="ti ti-loader-2" /> Descargando…</>
              : <><i aria-hidden="true" className="ti ti-download" /> Descargar documento</>}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
