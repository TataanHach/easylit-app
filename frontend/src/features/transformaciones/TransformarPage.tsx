/**
 * Wizard de transformar.
 *
 * Paso 1: el usuario sube el Excel de la licitación y elige la plantilla destino.
 * Al crear, el backend dispara el worker (limpieza + IA) y devuelve la
 * transformación. Entonces hacemos polling del estado hasta EN_REVISION o ERROR.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { plantillaService } from "@/features/plantillas/plantillaService";
import { transformacionService } from "@/features/historial/historialService";
import "./transformar.css";

export default function TransformarPage() {
  const navigate = useNavigate();
  const [archivo, setArchivo] = useState<File | null>(null);
  const [plantillaId, setPlantillaId] = useState("");
  const [mandante, setMandante] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");

  const { data: plantillas, isLoading: cargandoPlantillas } = useQuery({
    queryKey: ["plantillas"],
    queryFn: plantillaService.listar,
  });

  async function transformar() {
    if (!archivo || !plantillaId) return;
    setError("");
    setEnviando(true);
    try {
      const t = await transformacionService.crear({
        archivo, plantilla: plantillaId, mandante: mandante || undefined,
      });
      // Navegar a la URL propia de la transformación. Así el estado vive en el
      // backend (no en la memoria de esta pantalla): si el usuario se va y
      // vuelve, la transformación sigue en el historial y Transformar queda
      // limpio para empezar otra.
      navigate(`/transformar/${t.id}/mapeo`);
    } catch (e: any) {
      const detalle = e?.response?.data;
      setError(
        typeof detalle === "object"
          ? Object.values(detalle).flat().join(" ")
          : "No se pudo crear la transformación. Revisa el archivo y la plantilla."
      );
      setEnviando(false);
    }
  }

  const listo = archivo && plantillaId && !enviando;

  return (
    <div style={{ maxWidth: 860 }}>
      <div className="wizard-header">
        <h1>Nueva transformación</h1>
        <p>Sube la licitación en Excel y elige el formato del mandante al que transformarla.</p>
      </div>

      <div className="stepper">
        <div className="step activo"><span className="step-num">1</span> Cargar</div>
        <div className="step-linea" />
        <div className="step"><span className="step-num">2</span> Limpieza + IA</div>
        <div className="step-linea" />
        <div className="step"><span className="step-num">3</span> Revisar mapeo</div>
        <div className="step-linea" />
        <div className="step"><span className="step-num">4</span> Generar</div>
      </div>

      {error && (
        <div className="error-caja" style={{ marginBottom: "var(--s-4)" }}>
          <i className="ti ti-alert-circle" /><span>{error}</span>
        </div>
      )}

      <div className="carga-grid">
        <div className={`slot origen ${archivo ? "lleno" : ""}`}>
          <p className="slot-label">Documento fuente</p>
          {!archivo ? (
            <label className="dropzone">
              <input type="file" accept=".xlsx,.xls,.csv" style={{ display: "none" }}
                onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
              <div className="drop-icon"><i className="ti ti-file-upload" /></div>
              <p className="drop-title">Sube la licitación</p>
              <p className="drop-sub">Excel o CSV · haz clic para seleccionar</p>
            </label>
          ) : (
            <div className="archivo-card">
              <span className="archivo-icon"><i className="ti ti-file-spreadsheet" /></span>
              <div className="archivo-info">
                <p className="archivo-nombre">{archivo.name}</p>
                <p className="archivo-meta">{(archivo.size / 1024).toFixed(0)} KB</p>
              </div>
              <button className="quitar-btn" onClick={() => setArchivo(null)} title="Quitar">
                <i className="ti ti-x" />
              </button>
            </div>
          )}
        </div>

        <div className="flecha-col">
          <div className="flecha-circulo"><i className="ti ti-arrow-right" /></div>
        </div>

        <div className={`slot destino ${plantillaId ? "lleno" : ""}`}>
          <p className="slot-label">Formato destino</p>
          <div className="campo">
            <label>Plantilla del mandante</label>
            {cargandoPlantillas ? (
              <p className="drop-sub">Cargando plantillas…</p>
            ) : plantillas && plantillas.length > 0 ? (
              <select className="select-plantilla" value={plantillaId}
                onChange={(e) => setPlantillaId(e.target.value)}>
                <option value="">Elige una plantilla…</option>
                {plantillas.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre}{p.mandante ? ` · ${p.mandante}` : ""}
                  </option>
                ))}
              </select>
            ) : (
              <div className="error-caja">
                <i className="ti ti-info-circle" />
                <span>No hay plantillas. Crea una primero desde el admin.</span>
              </div>
            )}
          </div>
          <div className="campo">
            <label>Mandante (opcional)</label>
            <input type="text" placeholder="Ej. Codelco, MOP…"
              value={mandante} onChange={(e) => setMandante(e.target.value)} />
          </div>
        </div>
      </div>

      <div className="acciones">
        <span className="acciones-info">
          {!archivo && "Sube un archivo para empezar."}
          {archivo && !plantillaId && "Ahora elige la plantilla destino."}
          {archivo && plantillaId && "Todo listo para transformar."}
        </span>
        <button className="btn btn-primary btn-lg" disabled={!listo} onClick={transformar}
          style={!listo ? { opacity: 0.5, cursor: "not-allowed" } : {}}>
          {enviando ? "Subiendo…" : <>Transformar <i className="ti ti-arrow-right" /></>}
        </button>
      </div>
    </div>
  );
}