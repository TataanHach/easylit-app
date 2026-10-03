/**
 * Editor de mapeo + vista previa por hojas.
 *
 * La vista previa ahora va ARRIBA, muestra una HOJA A LA VEZ (navegable con
 * flechas), e incluye tanto los campos de formulario como los itemizados
 * (tablas de materiales/personal).
 */
import { useEffect, useState } from "react";
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
  const [mapeosLocal, setMapeosLocal] = useState<any[]>([]);
  const [guardandoId, setGuardandoId] = useState<string | null>(null);
  const [limpiando, setLimpiando] = useState(false);
  const [mensajeIA, setMensajeIA] = useState("");
  const [hojaActiva, setHojaActiva] = useState(0);

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

  const { data: preview, refetch: refetchPreview } = useQuery({
    queryKey: ["vistaPrevia", id],
    queryFn: () => transformacionService.vistaPrevia(id!),
    enabled: !!id && !!t && t.estado === "EN_REVISION",
  });

  useEffect(() => {
    if (t?.mapeos) setMapeosLocal(t.mapeos);
  }, [t?.mapeos]);

  async function cambiarDestino(mapeoId: string, destinoCampoId: string) {
    setMapeosLocal((prev) =>
      prev.map((m) => (m.id === mapeoId ? { ...m, destino_campo: destinoCampoId || null } : m))
    );
    setGuardandoId(mapeoId);
    try {
      await transformacionService.editarMapeo(mapeoId, destinoCampoId || null);
      await refetchPreview();
    } catch {
      alert("No se pudo guardar el cambio. Intenta de nuevo.");
    } finally {
      setGuardandoId(null);
    }
  }

  async function limpiarConIA() {
    if (!id) return;
    setLimpiando(true);
    setMensajeIA("");
    try {
      const r = await transformacionService.limpiarIA(id);
      if (r.modelo && (r.modelo.startsWith("gemini") || r.modelo.startsWith("models/"))) {
        setMensajeIA(`IA limpió ${r.campos} campo(s).`);
      } else if (r.modelo === "sin-limpieza-ia") {
        setMensajeIA("No había datos de texto para limpiar, o falta clave de IA.");
      } else {
        setMensajeIA("La IA no pudo limpiar ahora.");
      }
      await refetchPreview();
    } catch {
      setMensajeIA("No se pudo limpiar con IA. Revisa tu conexión o cuota.");
    } finally {
      setLimpiando(false);
    }
  }

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

  if (t.estado === "BORRADOR" || t.estado === "LIMPIEZA" || t.estado === "MAPEO_PROPUESTO") {
    return <ProcesandoIA estado={t.estado} nombre={t.nombre_origen} />;
  }

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

  const mapeos = mapeosLocal;
  const campos = plantilla?.campos ?? [];
  const hojas = preview?.hojas ?? [];
  const hoja = hojas[hojaActiva];

  return (
    <div style={{ maxWidth: 980 }}>
      <div className="mapeo-header">
        <h1>Revisar y generar</h1>
        <p>{t.nombre_origen} → {t.plantilla_nombre}. Revisa la vista previa por hoja, corrige lo que falte y genera.</p>
      </div>

      {/* ───── VISTA PREVIA POR HOJAS (arriba) ───── */}
      {hojas.length > 0 && (
        <div className="mapeo-panel" style={{ marginBottom: 18 }}>
          <div className="preview-nav">
            <button className="preview-flecha" disabled={hojaActiva === 0}
              onClick={() => setHojaActiva((h) => Math.max(0, h - 1))}>
              <i className="ti ti-chevron-left" />
            </button>
            <div className="preview-titulo">
              <span className="preview-hoja-nombre">{hoja?.nombre}</span>
              <span className="preview-hoja-contador">
                Hoja {hojaActiva + 1} de {hojas.length}
                {hoja?.tipo === "itemizado" && <span className="preview-badge-item">tabla</span>}
              </span>
            </div>
            <button className="preview-flecha" disabled={hojaActiva >= hojas.length - 1}
              onClick={() => setHojaActiva((h) => Math.min(hojas.length - 1, h + 1))}>
              <i className="ti ti-chevron-right" />
            </button>
          </div>

          {/* Contenido de la hoja activa */}
          {hoja?.tipo === "formulario" && (
            <table className="preview-tabla">
              <thead><tr><th>Campo</th><th>Valor final</th><th></th></tr></thead>
              <tbody>
                {hoja.campos.map((f: any, i: number) => (
                  <tr key={i}>
                    <td>{f.campo}</td>
                    <td style={{ fontWeight: f.valor_final ? 500 : 400,
                                 color: f.valor_final ? "var(--text)" : "var(--text-3)" }}>
                      {f.valor_final || "(vacío)"}
                    </td>
                    <td>{f.limpiado_ia && <span title="Limpiado con IA" style={{ color: "var(--ai-600,#5B4E8C)" }}><i className="ti ti-sparkles" /></span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {hoja?.tipo === "itemizado" && (
            <div style={{ overflowX: "auto" }}>
              <table className="preview-tabla preview-itemizado">
                <thead>
                  <tr>{hoja.tabla.columnas.map((c: string, i: number) => <th key={i}>{c}</th>)}</tr>
                </thead>
                <tbody>
                  {hoja.tabla.filas.map((fila: string[], i: number) => (
                    <tr key={i}>
                      {fila.map((celda, j) => <td key={j}>{celda || "—"}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ───── MAPEO (abajo) ───── */}
      <div className="mapeo-panel">
        <div className="mapeo-panel-head">
          <div className="titulo">
            <span className="mapeo-ia-icon"><i className="ti ti-brain" /></span>
            <div>
              <h2>Mapeo propuesto</h2>
              <p>Corrige cada destino si hace falta. Se guarda al instante.</p>
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
                  value={m.destino_campo ?? ""}
                  onChange={(e) => cambiarDestino(m.id, e.target.value)}
                >
                  <option value="">— Sin asignar —</option>
                  {campos.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.hoja_destino ? `[${c.hoja_destino}] ` : ""}{c.nombre}
                    </option>
                  ))}
                </select>
                <span className={`mapeo-conf ${clase}`}>
                  {guardandoId === m.id ? (
                    <i className="ti ti-loader-2" style={{ animation: "girar 1s linear infinite", color: "var(--brand-500)" }} />
                  ) : (
                    <>
                      <span className="mapeo-conf-bar"><span className="mapeo-conf-fill" style={{ width: `${m.confianza}%` }} /></span>
                      <span className="mapeo-conf-num">{m.confianza}%</span>
                    </>
                  )}
                </span>
              </div>
            );
          })
        )}
      </div>

      <div className="mapeo-acciones">
        <span className="mapeo-acciones-info">
          <i className="ti ti-info-circle" style={{ verticalAlign: "-2px" }} /> {mapeos.length} campos.
          {mensajeIA && <span style={{ marginLeft: 10, color: "var(--ai-600, #5B4E8C)", fontWeight: 600 }}>{mensajeIA}</span>}
        </span>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-lg" onClick={() => navigate("/historial")}>Volver</button>
          <button className="btn btn-lg" onClick={limpiarConIA} disabled={limpiando}
            style={{ borderColor: "var(--ai-600, #5B4E8C)", color: "var(--ai-600, #5B4E8C)" }}>
            {limpiando ? "Limpiando…" : <><i className="ti ti-sparkles" /> Limpiar con IA</>}
          </button>
          <button className="btn btn-primary btn-lg" onClick={generar} disabled={generando || mapeos.length === 0}>
            {generando ? "Generando…" : <><i className="ti ti-file-export" /> Generar documento</>}
          </button>
        </div>
      </div>
    </div>
  );
}

function ProcesandoIA({ estado, nombre }: { estado: string; nombre: string }) {
  const pasoActual =
    estado === "BORRADOR" ? 0 :
      estado === "LIMPIEZA" ? 1 :
        estado === "MAPEO_PROPUESTO" ? 2 : 3;
  const pasos = [
    { icono: "ti ti-file-search", titulo: "Leyendo el documento", desc: "Extrayendo las columnas y datos del Excel" },
    { icono: "ti ti-wash", titulo: "Limpiando los datos", desc: "Duplicados, unidades y formatos numéricos" },
    { icono: "ti ti-brain", titulo: "La IA está trabajando", desc: "Gemini analiza y propone el mapeo de campos", ia: true },
    { icono: "ti ti-checks", titulo: "Preparando la revisión", desc: "Dejando todo listo para que revises" },
  ];
  return (
    <div style={{ maxWidth: 620 }}>
      <div className="mapeo-header"><h1>Procesando tu licitación</h1><p>{nombre}</p></div>
      <div className="ia-proceso">
        <div className="ia-proceso-orbe"><i className="ti ti-sparkles" /></div>
        <div className="ia-pasos">
          {pasos.map((p, i) => {
            const hecho = i < pasoActual; const activo = i === pasoActual;
            return (
              <div key={i} className={`ia-paso ${hecho ? "hecho" : ""} ${activo ? "activo" : ""}`}>
                <span className="ia-paso-icono">{hecho ? <i className="ti ti-check" /> : <i className={p.icono} />}</span>
                <div className="ia-paso-texto">
                  <p className="ia-paso-titulo">{p.titulo}{p.ia && activo && <span className="ia-badge">IA</span>}</p>
                  <p className="ia-paso-desc">{p.desc}</p>
                </div>
                {activo && <span className="ia-paso-spinner"><i className="ti ti-loader-2" /></span>}
              </div>
            );
          })}
        </div>
        <p className="ia-nota"><i className="ti ti-info-circle" /> Puedes ir a otras secciones; la transformación seguirá en tu historial.</p>
      </div>
    </div>
  );
}