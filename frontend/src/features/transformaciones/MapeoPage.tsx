/**
 * Editor de mapeo (paso 3-4 en una pantalla).
 *
 * Carga el detalle de una transformación, muestra cada correspondencia
 * origen→destino que propuso la IA con su confianza, permite corregir el campo
 * destino, y ofrece aprobar → generar → descargar.
 */
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { plantillaService } from "@/features/plantillas/plantillaService";
import { transformacionService } from "@/features/historial/historialService";
import "./mapeo.css";

export default function MapeoPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [generando, setGenerando] = useState(false);
  const [generado, setGenerado] = useState(false);

  const { data: t, isLoading, refetch } = useQuery({
    queryKey: ["transformacion", id],
    queryFn: () => transformacionService.detalle(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const estado = query.state.data?.estado;
      const enProceso = estado === "BORRADOR" || estado === "LIMPIEZA" || estado === "MAPEO_PROPUESTO";
      return enProceso ? 2000 : false;
    },
  });

  const { data: plantilla } = useQuery({
    queryKey: ["plantilla", t?.plantilla],
    queryFn: () => plantillaService.detalle(t!.plantilla),
    enabled: !!t?.plantilla,
  });

  async function generar() {
    if (!id) return;
    setGenerando(true);
    try {
      await transformacionService.generar(id);
      await refetch();
      setGenerado(true);
    } catch {
      alert("No se pudo generar el documento. Revisa que haya un worker o intenta de nuevo.");
    } finally {
      setGenerando(false);
    }
  }

  async function descargar() {
    if (!id || !t) return;
    try {
      await transformacionService.descargar(id, `${t.nombre_origen}_transformado.xlsx`);
    } catch {
      alert("No se pudo descargar el documento. Intenta de nuevo.");
    }
  }

  if (isLoading) {
    return <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>Cargando…</div>;
  }
  if (!t) {
    return <div style={{ padding: 40, textAlign: "center" }}>No se encontró la transformación.</div>;
  }

  // ── Pantalla "la IA está trabajando" con pasos animados ──
  if (t.estado === "BORRADOR" || t.estado === "LIMPIEZA" || t.estado === "MAPEO_PROPUESTO") {
    return <ProcesandoIA estado={t.estado} nombre={t.nombre_origen} />;
  }

  // Error de procesamiento.
  if (t.estado === "ERROR") {
    return (
      <div style={{ maxWidth: 640 }}>
        <div className="mapeo-header"><h1>Hubo un problema</h1></div>
        <div style={{
          background: "var(--danger-50)", border: "1px solid #f2c9c9",
          borderRadius: "var(--r-lg)", padding: 24, color: "var(--danger-700)",
        }}>
          <i className="ti ti-alert-triangle" style={{ fontSize: 28 }} />
          <p style={{ marginTop: 8 }}><strong>No se pudo procesar el archivo.</strong></p>
          <p style={{ marginTop: 4 }}>{t.detalle_error || "Revisa que el Excel sea válido."}</p>
          <button className="btn btn-lg" style={{ marginTop: 16 }} onClick={() => navigate("/transformar")}>
            Intentar con otro archivo
          </button>
        </div>
      </div>
    );
  }

  // Éxito tras generar.
  if (generado || t.estado === "GENERADO") {
    return (
      <div style={{ maxWidth: 640 }}>
        <div className="mapeo-header"><h1>Documento generado</h1></div>
        <div className="exito-caja">
          <i className="ti ti-circle-check" />
          <h2>¡Tu documento está listo!</h2>
          <p>Se rellenó la plantilla con los datos de la licitación, respetando el formato original.</p>
          <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
            <button className="btn btn-primary btn-lg" onClick={descargar}>
              <i className="ti ti-download" /> Descargar documento
            </button>
            <button className="btn btn-lg" onClick={() => navigate("/historial")}>
              Ir al historial
            </button>
          </div>
        </div>
      </div>
    );
  }

  const mapeos = t.mapeos ?? [];
  const campos = plantilla?.campos ?? [];

  return (
    <div style={{ maxWidth: 980 }}>
      <div className="mapeo-header">
        <h1>Revisar mapeo</h1>
        <p>{t.nombre_origen} → {t.plantilla_nombre}. Revisa lo que propuso la IA y genera el documento.</p>
      </div>

      <div className="mapeo-panel">
        <div className="mapeo-panel-head">
          <div className="titulo">
            <span className="mapeo-ia-icon"><i className="ti ti-brain" /></span>
            <div>
              <h2>Mapeo propuesto</h2>
              <p>Nada se aplica hasta que generes el documento.</p>
            </div>
          </div>
          <span className="privacy-tag"><i className="ti ti-lock" /> Montos ocultos a la IA</span>
        </div>

        {mapeos.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--text-3)" }}>
            No hay mapeos. Puede que el procesamiento aún no termine.
          </div>
        ) : (
          mapeos.map((m) => {
            const clase = m.confianza >= 85 ? "alta" : m.confianza >= 60 ? "media" : "baja";
            return (
              <div className="mapeo-fila" key={m.id}>
                <span className="mapeo-origen">{m.origen_columna}</span>
                <span className="mapeo-flecha"><i className="ti ti-arrow-right" /></span>
                <select
                  className={`mapeo-select ${!m.destino_campo ? "sin-asignar" : ""}`}
                  defaultValue={m.destino_campo ?? ""}
                >
                  <option value="">— Sin asignar —</option>
                  {campos.map((c) => (
                    <option key={c.id} value={c.id}>{c.nombre}</option>
                  ))}
                </select>
                <span className={`mapeo-conf ${clase}`}>
                  <span className="mapeo-conf-bar"><span className="mapeo-conf-fill" style={{ width: `${m.confianza}%` }} /></span>
                  <span className="mapeo-conf-num">{m.confianza}%</span>
                </span>
              </div>
            );
          })
        )}
      </div>

      <div className="mapeo-acciones">
        <span className="mapeo-acciones-info">
          <i className="ti ti-info-circle" style={{ verticalAlign: "-2px" }} /> {mapeos.length} campos mapeados.
          Al generar, se rellenará la plantilla con estos datos.
        </span>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-lg" onClick={() => navigate("/historial")}>Volver</button>
          <button className="btn btn-primary btn-lg" onClick={generar} disabled={generando || mapeos.length === 0}>
            {generando ? "Generando…" : <><i className="ti ti-file-export" /> Generar documento</>}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Pantalla animada de procesamiento. Los pasos se van marcando según el estado
 * real que reporta el backend:
 *   BORRADOR        -> empezando (paso 1 activo)
 *   LIMPIEZA        -> limpieza hecha, IA trabajando (paso 2 activo)
 *   MAPEO_PROPUESTO -> mapeo casi listo (paso 3 activo)
 */
function ProcesandoIA({ estado, nombre }: { estado: string; nombre: string }) {
  // A qué paso corresponde cada estado (0-indexed): cuáles están hechos y cuál activo.
  const pasoActual =
    estado === "BORRADOR" ? 0 :
    estado === "LIMPIEZA" ? 1 :
    estado === "MAPEO_PROPUESTO" ? 2 : 3;

  const pasos = [
    { icono: "ti ti-file-search",    titulo: "Leyendo el documento",        desc: "Extrayendo las columnas y datos del Excel" },
    { icono: "ti ti-wash",           titulo: "Limpiando los datos",         desc: "Duplicados, unidades y formatos numéricos" },
    { icono: "ti ti-brain",          titulo: "La IA está trabajando",       desc: "Gemini analiza y propone el mapeo de campos", ia: true },
    { icono: "ti ti-checks",         titulo: "Preparando la revisión",      desc: "Dejando todo listo para que revises" },
  ];

  return (
    <div style={{ maxWidth: 620 }}>
      <div className="mapeo-header">
        <h1>Procesando tu licitación</h1>
        <p>{nombre}</p>
      </div>

      <div className="ia-proceso">
        <div className="ia-proceso-orbe">
          <i className="ti ti-sparkles" />
        </div>

        <div className="ia-pasos">
          {pasos.map((p, i) => {
            const hecho = i < pasoActual;
            const activo = i === pasoActual;
            return (
              <div key={i} className={`ia-paso ${hecho ? "hecho" : ""} ${activo ? "activo" : ""}`}>
                <span className="ia-paso-icono">
                  {hecho ? <i className="ti ti-check" /> : <i className={p.icono} />}
                </span>
                <div className="ia-paso-texto">
                  <p className="ia-paso-titulo">
                    {p.titulo}
                    {p.ia && activo && <span className="ia-badge">IA</span>}
                  </p>
                  <p className="ia-paso-desc">{p.desc}</p>
                </div>
                {activo && <span className="ia-paso-spinner"><i className="ti ti-loader-2" /></span>}
              </div>
            );
          })}
        </div>

        <p className="ia-nota">
          <i className="ti ti-info-circle" /> Puedes ir a otras secciones; la transformación seguirá en tu historial.
        </p>
      </div>
    </div>
  );
}