/**
 * Editor de mapeo + vista previa por hojas.
 *
 * Orden: Vista previa (arriba) → BOTONES (medio) → Mapeo (abajo).
 * En la vista previa, los campos de moneda tienen un control de IVA que
 * reemplaza el de la plantilla para esta transformación.
 */
import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { plantillaService } from "@/features/plantillas/plantillaService";
import { transformacionService } from "@/features/historial/historialService";
import { useAvisos } from "@/components/ui/Avisos";
import { describirError } from "@/lib/errores";
import "./mapeo.css";

const IVA_OPCIONES = [
  { v: "NINGUNO", t: "Sin IVA" },
  { v: "AGREGAR", t: "+ IVA (19%)" },
  { v: "QUITAR", t: "Neto (−IVA)" },
];

export default function MapeoPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const avisos = useAvisos();
  const [generando, setGenerando] = useState(false);
  const [generado, setGenerado] = useState(false);
  const [mapeosLocal, setMapeosLocal] = useState<any[]>([]);
  const [guardandoId, setGuardandoId] = useState<string | null>(null);
  const [limpiando, setLimpiando] = useState(false);
  const [hojaActiva, setHojaActiva] = useState(0);

  const { data: t, isLoading, isFetchedAfterMount, refetch } = useQuery({
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

  // Mientras el worker procesa se muestra la animación de pasos. Aunque el
  // backend termine, la animación completa los pasos que faltan antes de pasar
  // a la revisión (si no, los pasos rápidos ni se alcanzan a ver).
  // Solo cuenta el estado consultado al abrir la pantalla: el de la caché puede
  // ser viejo (ej. quedó en LIMPIEZA y ya está EN_REVISION) y lanzaría la
  // animación de nuevo.
  const estadoEnProceso = t?.estado === "BORRADOR" || t?.estado === "LIMPIEZA" || t?.estado === "MAPEO_PROPUESTO";
  const enProceso = isFetchedAfterMount && estadoEnProceso;
  const [animandoProceso, setAnimandoProceso] = useState(false);
  useEffect(() => {
    if (enProceso) setAnimandoProceso(true);
  }, [enProceso]);

  // Si el procesamiento que se estaba mirando termina en error, avisarlo.
  const vioProceso = useRef(false);
  useEffect(() => {
    if (enProceso) vioProceso.current = true;
    if (vioProceso.current && t?.estado === "ERROR") {
      vioProceso.current = false;
      avisos.error(
        "El mapeo no se pudo completar",
        t.detalle_error || "Ocurrió un problema al procesar el archivo. Abajo verás qué hacer."
      );
    }
  }, [enProceso, t?.estado, t?.detalle_error, avisos]);

  /** Al terminar la animación: pasar a revisión y contar cómo salió el mapeo. */
  function terminarProceso() {
    setAnimandoProceso(false);
    vioProceso.current = false;
    if (!t || t.estado !== "EN_REVISION") return;

    const lista = t.mapeos ?? [];
    const total = lista.length;
    const asignados = lista.filter((m) => m.destino_campo).length;
    const confianza = t.confianza ?? 0;
    const avisoIA = t.resultado_limpieza?.aviso_ia as string | undefined;

    if (total === 0) {
      avisos.error(
        "El mapeo terminó sin datos",
        "No se encontraron columnas ni etiquetas en el archivo de origen. Revisa que el Excel tenga encabezados y valores, y crea una nueva transformación."
      );
    } else if (asignados === 0) {
      avisos.error(
        "El mapeo terminó, pero no se asignó ningún campo",
        "No se encontró a qué campo de la plantilla corresponde cada dato. Asígnalos a mano abajo, en «Mapeo propuesto», antes de generar."
      );
    } else if (avisoIA) {
      avisos.advertencia(
        "Mapeo listo, pero sin IA",
        `${asignados} de ${total} datos tienen campo destino. ${avisoIA}`
      );
    } else if (asignados < total || confianza < 60) {
      avisos.advertencia(
        "Mapeo listo: revisa algunos campos",
        `${asignados} de ${total} datos tienen campo destino, con ${confianza}% de confianza promedio. Revisa los que están sin asignar o con confianza baja antes de generar.`
      );
    } else {
      avisos.exito(
        "Mapeo realizado con éxito",
        `Los ${total} datos tienen campo destino, con ${confianza}% de confianza promedio. Revisa la vista previa y genera el documento.`
      );
    }
  }

  async function cambiarDestino(mapeoId: string, destinoCampoId: string) {
    setMapeosLocal((prev) =>
      prev.map((m) => (m.id === mapeoId ? { ...m, destino_campo: destinoCampoId || null } : m))
    );
    setGuardandoId(mapeoId);
    try {
      await transformacionService.editarMapeo(mapeoId, destinoCampoId || null);
      await refetchPreview();
    } catch (e) {
      // Volver al valor guardado para no mostrar un cambio que no se aplicó.
      setMapeosLocal(t?.mapeos ?? []);
      avisos.error(describirError(e, "guardar el cambio de campo"));
    } finally {
      setGuardandoId(null);
    }
  }

  async function cambiarIVA(campoNombre: string, ajuste: string) {
    if (!id) return;
    try {
      await transformacionService.ajustarIVA(id, campoNombre, ajuste);
      await refetchPreview();
    } catch (e) {
      avisos.error(describirError(e, `ajustar el IVA de «${campoNombre}»`));
    }
  }

  async function limpiarConIA() {
    if (!id) return;
    setLimpiando(true);
    try {
      const r = await transformacionService.limpiarIA(id);
      if (r.modelo && (r.modelo.startsWith("gemini") || r.modelo.startsWith("models/"))) {
        avisos.exito(
          "Limpieza con IA lista",
          r.campos > 0
            ? `Se limpiaron ${r.campos} campo(s) de texto y fechas. Revisa la vista previa antes de generar.`
            : "La IA revisó los datos y no encontró nada que corregir."
        );
      } else if (r.modelo === "sin-limpieza-ia") {
        avisos.info(
          "No había nada que limpiar",
          "Los campos mapeados no tienen texto ni fechas con valor. Los montos nunca se envían a la IA."
        );
      } else if (r.modelo === "sin-clave-ia") {
        avisos.error(
          "La IA no está configurada",
          "Falta la clave de Gemini en el servidor (GEMINI_API_KEY). Pídele al administrador que la configure. Puedes generar el documento igual."
        );
      } else {
        avisos.error(
          "La IA no pudo limpiar los datos",
          "Puede que se haya agotado la cuota de Gemini o no haya conexión. Los datos quedaron como estaban: puedes generar igual o intentarlo más tarde."
        );
      }
      await refetchPreview();
    } catch (e) {
      avisos.error(describirError(e, "limpiar los datos con IA"));
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
      avisos.exito("Transformación realizada con éxito", "El documento está listo para descargar.");
    } catch (e) {
      avisos.error(describirError(e, "generar el documento"));
      await refetch();
    } finally {
      setGenerando(false);
    }
  }

  async function descargar() {
    if (!id || !t) return;
    try {
      const archivo = t.nombre ? `${t.nombre}.xlsx` : `${t.nombre_origen}_transformado.xlsx`;
      await transformacionService.descargar(id, archivo);
      avisos.exito("Descarga iniciada", `«${archivo}» se está guardando en tu carpeta de descargas.`);
    } catch (e) {
      avisos.error(describirError(e, "descargar el documento"));
    }
  }

  if (isLoading || (estadoEnProceso && !isFetchedAfterMount)) {
    return <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>
      <i className="ti ti-loader-2" style={{ fontSize: 22 }} /><p style={{ marginTop: 8 }}>Cargando…</p>
    </div>;
  }
  if (!t) {
    return (
      <div style={{ maxWidth: 640 }}>
        <div className="banda banda-error">
          <i className="ti ti-alert-circle" />
          <div>
            <strong>No se encontró la transformación</strong>
            Puede que se haya eliminado o que no tengas acceso a ella. Vuelve al historial y elige otra.
          </div>
        </div>
        <button className="btn btn-lg" onClick={() => navigate("/historial")}>Ir al historial</button>
      </div>
    );
  }

  if (t.estado !== "ERROR" && (enProceso || animandoProceso)) {
    return (
      <ProcesandoIA estado={t.estado} nombre={t.nombre || t.nombre_origen}
        onTerminar={terminarProceso} />
    );
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
          <p style={{ marginTop: 8 }}><strong>No se pudo procesar «{t.nombre || t.nombre_origen}».</strong></p>
          <p style={{ marginTop: 12, fontWeight: 600 }}>¿Qué pasó?</p>
          <p style={{ marginTop: 2 }}>
            {t.detalle_error || "El archivo no se pudo leer. Puede que no sea un Excel válido o que esté dañado."}
          </p>
          <p style={{ marginTop: 12, fontWeight: 600 }}>¿Qué puedes hacer?</p>
          <p style={{ marginTop: 2 }}>
            Corrige el archivo según lo indicado y crea una nueva transformación. Esta quedará en el historial con estado «Error».
          </p>
          <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
            <button className="btn btn-primary btn-lg" onClick={() => navigate("/transformar")}>
              Intentar con otro archivo
            </button>
            <button className="btn btn-lg" onClick={() => navigate("/historial")}>Ir al historial</button>
          </div>
        </div>
      </div>
    );
  }

  if (generado || t.estado === "GENERADO") {
    return (
      <div style={{ maxWidth: 640 }}>
        <div className="mapeo-header"><h1>Transformación realizada con éxito</h1></div>
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

  // Advertencias antes de generar.
  const avisoIA = t.resultado_limpieza?.aviso_ia as string | undefined;
  const sinAsignar = mapeos.filter((m) => !m.destino_campo).length;
  const ningunoAsignado = mapeos.length > 0 && sinAsignar === mapeos.length;
  const obligatoriosFaltantes = campos.filter(
    (c) => c.obligatorio && !mapeos.some((m) => m.destino_campo === c.id)
  );

  return (
    <div style={{ maxWidth: 980 }}>
      <div className="mapeo-header">
        <h1>Revisar y generar</h1>
        <p>{t.nombre || t.nombre_origen} → {t.plantilla_nombre}. Revisa la vista previa, ajusta y genera.</p>
      </div>

      {/* ───── VISTA PREVIA POR HOJAS (arriba) ───── */}
      {hojas.length > 0 && (
        <div className="mapeo-panel" style={{ marginBottom: 14 }}>
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

          {hoja?.tipo === "formulario" && (
            <table className="preview-tabla">
              <thead><tr><th>Campo</th><th>Valor final</th><th>IVA</th><th></th></tr></thead>
              <tbody>
                {hoja.campos.map((f: any, i: number) => (
                  <tr key={i}>
                    <td>{f.campo}</td>
                    <td style={{ fontWeight: f.valor_final ? 500 : 400,
                                 color: f.valor_final ? "var(--text)" : "var(--text-3)" }}>
                      {f.valor_final || "(vacío)"}
                    </td>
                    <td>
                      {f.es_moneda && (
                        <select className="iva-select" value={f.ajuste_iva || "NINGUNO"}
                          onChange={(e) => cambiarIVA(f.campo, e.target.value)}>
                          {IVA_OPCIONES.map((o) => <option key={o.v} value={o.v}>{o.t}</option>)}
                        </select>
                      )}
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
                    <tr key={i}>{fila.map((celda, j) => <td key={j}>{celda || "—"}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ───── ADVERTENCIAS ───── */}
      {avisoIA && (
        <div className="banda banda-aviso">
          <i className="ti ti-alert-triangle" />
          <div><strong>Mapeo hecho sin IA</strong>{avisoIA}</div>
        </div>
      )}
      {ningunoAsignado ? (
        <div className="banda banda-error">
          <i className="ti ti-alert-circle" />
          <div>
            <strong>No se puede generar todavía</strong>
            Ningún dato tiene un campo destino, así que el documento saldría vacío. Abajo, en «Mapeo propuesto»,
            elige a qué campo de la plantilla va cada dato.
          </div>
        </div>
      ) : obligatoriosFaltantes.length > 0 && (
        <div className="banda banda-aviso">
          <i className="ti ti-alert-triangle" />
          <div>
            <strong>Faltan campos obligatorios</strong>
            Ningún dato está asignado a: {obligatoriosFaltantes.map((c) => c.nombre).join(", ")}. Quedarán vacíos en el
            documento. Asígnalos abajo si el dato existe en el origen.
          </div>
        </div>
      )}

      {/* ───── BOTONES (entre vista previa y mapeo) ───── */}
      <div className="mapeo-acciones" style={{ marginBottom: 14 }}>
        <span className="mapeo-acciones-info">
          <i className="ti ti-info-circle" style={{ verticalAlign: "-2px" }} /> {mapeos.length} campos
          {sinAsignar > 0 && !ningunoAsignado && <> · {sinAsignar} sin asignar (no se incluirán)</>}.
        </span>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-lg" onClick={() => navigate("/historial")}>Volver</button>
          <button className="btn btn-lg" onClick={limpiarConIA} disabled={limpiando}
            style={{ borderColor: "var(--ai-600, #5B4E8C)", color: "var(--ai-600, #5B4E8C)" }}>
            {limpiando ? "Limpiando…" : <><i className="ti ti-sparkles" /> Limpiar con IA</>}
          </button>
          <button className="btn btn-primary btn-lg" onClick={generar}
            disabled={generando || mapeos.length === 0 || ningunoAsignado}
            title={ningunoAsignado ? "Asigna al menos un campo destino para poder generar" : undefined}>
            {generando ? "Generando…" : <><i className="ti ti-file-export" /> Generar documento</>}
          </button>
        </div>
      </div>

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
            No se encontraron datos para mapear en el archivo de origen. Revisa que el Excel tenga encabezados y
            valores, y crea una nueva transformación.
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
    </div>
  );
}

// Tiempo mínimo que se ve cada paso, para que la animación se lea aunque el
// worker sea más rápido que el sondeo de 2 s.
const MS_POR_PASO = 900;

function ProcesandoIA({ estado, nombre, onTerminar }: {
  estado: string; nombre: string; onTerminar: () => void;
}) {
  // Hasta qué paso llegó realmente el worker (índice del paso en curso):
  //   BORRADOR        → leyendo/limpiando el Excel (pasos 0 y 1)
  //   LIMPIEZA        → limpieza lista, la IA está trabajando (paso 2)
  //   MAPEO_PROPUESTO → la IA respondió, se guarda el mapeo (paso 3)
  //   EN_REVISION…    → todo listo (4 = todos hechos)
  const objetivo =
    estado === "BORRADOR" ? 1 :
      estado === "LIMPIEZA" ? 2 :
        estado === "MAPEO_PROPUESTO" ? 3 : 4;

  // El paso mostrado avanza de a uno hacia el objetivo, con un mínimo por paso.
  const [pasoActual, setPasoActual] = useState(0);
  // En ref para que los re-render del padre (sondeo) no reinicien el temporizador.
  const onTerminarRef = useRef(onTerminar);
  onTerminarRef.current = onTerminar;
  useEffect(() => {
    if (pasoActual < objetivo) {
      const timer = setTimeout(() => setPasoActual((p) => p + 1), MS_POR_PASO);
      return () => clearTimeout(timer);
    }
    if (pasoActual >= 4) {
      const timer = setTimeout(() => onTerminarRef.current(), 600);   // un respiro con todo en verde
      return () => clearTimeout(timer);
    }
  }, [pasoActual, objetivo]);

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