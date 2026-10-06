/**
 * Pantalla de historial.
 *
 * Muestra las transformaciones en una tabla, con el filtro Mías / De mi equipo /
 * Todas. Usa React Query para pedir los datos al backend y manejar los estados
 * de carga y error sin código manual. Cada tab cambia el parámetro `alcance` y
 * React Query vuelve a pedir (con caché por alcance).
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";
import { transformacionService, type Alcance } from "./historialService";
import { useAvisos } from "@/components/ui/Avisos";
import { describirError } from "@/lib/errores";
import type { Transformacion } from "@/types";
import "./historial.css";

const POR_PAGINA = 15;
const MAX_NOMBRE = 40;   // caracteres visibles del nombre en la tabla

const TABS: { clave: Alcance; label: string; icono: string }[] = [
  { clave: "mine", label: "Mías", icono: "ti ti-user" },
  { clave: "team", label: "De mi equipo", icono: "ti ti-users" },
  { clave: "all", label: "Todas", icono: "ti ti-building" },
];

export default function HistorialPage() {
  const { usuario } = useAuth();
  const [alcance, setAlcance] = useState<Alcance>("mine");
  const [pagina, setPagina] = useState(1);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["transformaciones", alcance],
    queryFn: () => transformacionService.listar(alcance),
    // Auto-actualizar cada 3s si hay alguna transformación en proceso, para que
    // los estados (Procesando → En revisión → Completada) se vean sin refrescar.
    // Cuando todas están en un estado final, deja de refrescar para no gastar.
    refetchInterval: (query) => {
      const filas = query.state.data;
      if (!filas) return false;
      const hayEnProceso = filas.some((t) =>
        t.estado === "BORRADOR" || t.estado === "LIMPIEZA" || t.estado === "MAPEO_PROPUESTO"
      );
      return hayEnProceso ? 3000 : false;
    },
  });

  // Filtros (se aplican sobre la lista ya cargada).
  const [filtroAutor, setFiltroAutor] = useState("");
  const [filtroEmpresa, setFiltroEmpresa] = useState("");
  const [fechaDesde, setFechaDesde] = useState("");
  const [fechaHasta, setFechaHasta] = useState("");
  const hayFiltros = !!(filtroAutor || filtroEmpresa || fechaDesde || fechaHasta);

  function limpiarFiltros() {
    setFiltroAutor(""); setFiltroEmpresa(""); setFechaDesde(""); setFechaHasta("");
  }

  // Opciones de los selects, sacadas de las filas cargadas.
  const autores = useMemo(() => {
    const mapa = new Map<string, string>();
    data?.forEach((t) => mapa.set(t.autor, t.autor_nombre ?? "—"));
    return Array.from(mapa, ([id, nombre]) => ({ id, nombre }))
      .sort((a, b) => a.nombre.localeCompare(b.nombre));
  }, [data]);

  const empresas = useMemo(() => {
    const set = new Set<string>();
    data?.forEach((t) => { const e = empresaDe(t); if (e) set.add(e); });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [data]);

  const filtradas = useMemo(() => (data ?? []).filter((t) => {
    if (filtroAutor && t.autor !== filtroAutor) return false;
    if (filtroEmpresa === "__sin__" && empresaDe(t)) return false;
    if (filtroEmpresa && filtroEmpresa !== "__sin__" && empresaDe(t) !== filtroEmpresa) return false;
    const dia = fechaLocal(t.creada);
    if (fechaDesde && dia < fechaDesde) return false;
    if (fechaHasta && dia > fechaHasta) return false;
    return true;
  }), [data, filtroAutor, filtroEmpresa, fechaDesde, fechaHasta]);

  // Al cambiar de pestaña o de filtro se vuelve a la primera página.
  useEffect(() => { setPagina(1); }, [alcance, filtroAutor, filtroEmpresa, fechaDesde, fechaHasta]);

  const totalPaginas = Math.max(1, Math.ceil(filtradas.length / POR_PAGINA));
  const paginaActual = Math.min(pagina, totalPaginas);   // por si se borraron filas
  const filasPagina = filtradas.slice((paginaActual - 1) * POR_PAGINA, paginaActual * POR_PAGINA);

  return (
    <>
      <div className="page-header">
        <h1>Historial de transformaciones</h1>
        <p>Licitaciones procesadas con la plataforma. Cada una conserva su bitácora.</p>
      </div>

      <div className="scope-tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.clave}
            className={`scope-tab ${alcance === t.clave ? "activo" : ""}`}
            onClick={() => setAlcance(t.clave)}
          >
            <i className={t.icono} /> {t.label}
          </button>
        ))}
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <span className="panel-title">Transformaciones</span>
            {data && <span className="panel-count">{filtradas.length} resultado{filtradas.length !== 1 ? "s" : ""}</span>}
          </div>
        </div>

        {data && data.length > 0 && (
          <div className="filtros">
            <label className="filtro">
              <span>Autor</span>
              <select value={filtroAutor} onChange={(e) => setFiltroAutor(e.target.value)}>
                <option value="">Todos</option>
                {autores.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
              </select>
            </label>
            <label className="filtro">
              <span>Empresa</span>
              <select value={filtroEmpresa} onChange={(e) => setFiltroEmpresa(e.target.value)}>
                <option value="">Todas</option>
                {empresas.map((e) => <option key={e} value={e}>{e}</option>)}
                {data.some((t) => !empresaDe(t)) && <option value="__sin__">Sin empresa</option>}
              </select>
            </label>
            <FechaInput label="Desde" value={fechaDesde} onChange={setFechaDesde}
              max={fechaHasta || undefined} />
            <FechaInput label="Hasta" value={fechaHasta} onChange={setFechaHasta}
              min={fechaDesde || undefined} />
            {hayFiltros && (
              <button className="btn filtros-limpiar" onClick={limpiarFiltros}>
                <i className="ti ti-x" /> Limpiar filtros
              </button>
            )}
          </div>
        )}

        {isLoading && (
          <div className="estado-caja">
            <i className="ti ti-loader-2" /><p style={{ marginTop: 8 }}>Cargando…</p>
          </div>
        )}

        {isError && (
          <div className="estado-caja">
            <i className="ti ti-alert-circle" style={{ color: "var(--danger-500)" }} />
            <h3>No se pudo cargar el historial</h3>
            <p>No hay conexión con el servidor. Revisa tu internet (o que el backend esté encendido) y recarga la página.</p>
          </div>
        )}

        {data && data.length === 0 && (
          <div className="estado-caja">
            <i className="ti ti-folder-open" />
            <h3>Nada por aquí todavía</h3>
            <p>No hay transformaciones con este filtro.</p>
          </div>
        )}

        {data && data.length > 0 && filtradas.length === 0 && (
          <div className="estado-caja">
            <i className="ti ti-filter-off" />
            <h3>Sin resultados</h3>
            <p>Ninguna transformación coincide con los filtros.</p>
          </div>
        )}

        {filtradas.length > 0 && (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Documento origen</th>
                  <th>Formato destino</th>
                  <th>Autor</th>
                  <th>Confianza</th>
                  <th>Estado</th>
                  <th>Fecha</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filasPagina.map((t) => (
                  <Fila key={t.id} t={t} esMio={t.autor === usuario?.id} />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data && totalPaginas > 1 && (
          <div className="paginacion">
            <span className="paginacion-info">
              {(paginaActual - 1) * POR_PAGINA + 1}–{Math.min(paginaActual * POR_PAGINA, filtradas.length)} de {filtradas.length}
            </span>
            <div className="paginacion-botones">
              <button className="btn" disabled={paginaActual === 1}
                onClick={() => setPagina(paginaActual - 1)} title="Anterior">
                <i className="ti ti-chevron-left" />
              </button>
              <span className="paginacion-num">Página {paginaActual} de {totalPaginas}</span>
              <button className="btn" disabled={paginaActual === totalPaginas}
                onClick={() => setPagina(paginaActual + 1)} title="Siguiente">
                <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function Fila({ t, esMio }: { t: Transformacion; esMio: boolean }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { usuario } = useAuth();
  const avisos = useAvisos();
  const [confirmar, setConfirmar] = useState(false);
  const [borrando, setBorrando] = useState(false);

  const empresa = empresaDe(t);
  const nombreVisible = t.nombre || t.nombre_origen;
  // Tooltip: el nombre completo si se recortó, y el archivo original si tiene nombre propio.
  const titulo = [
    nombreVisible.length > MAX_NOMBRE ? nombreVisible : "",
    t.nombre ? t.nombre_origen : "",
  ].filter(Boolean).join("\n") || undefined;
  const ext = t.nombre_origen.split(".").pop()?.toLowerCase();
  const iconoClase = ext === "xlsx" || ext === "csv" ? "xlsx" : "";
  const iconoArchivo =
    ext === "xlsx" || ext === "csv" ? "ti ti-file-spreadsheet" : "ti ti-file-type-pdf";

  const iniciales = (t.autor_nombre ?? "")
    .split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();

  // Puede borrar: el autor, o un gerente/superadmin.
  const puedeBorrar = esMio || usuario?.rol === "GERENTE" || usuario?.rol === "SUPERADMIN";

  async function eliminar() {
    setBorrando(true);
    try {
      await transformacionService.eliminar(t.id);
      queryClient.invalidateQueries({ queryKey: ["transformaciones"] });
      avisos.exito("Transformación eliminada", `«${nombreVisible}» se quitó del historial.`);
    } catch (e) {
      avisos.error(describirError(e, "eliminar la transformación"));
      setBorrando(false);
      setConfirmar(false);
    }
  }

  return (
    <tr>
      <td>
        <div className="doc-cell">
          <span className={`doc-icon ${iconoClase}`}><i className={iconoArchivo} /></span>
          <div>
            <p className="doc-name" title={titulo}>{recortar(nombreVisible, MAX_NOMBRE)}</p>
            {empresa && <p style={{ fontSize: "var(--fs-sm)", color: "var(--text-3)" }}>{empresa}</p>}
          </div>
        </div>
      </td>
      <td>{t.plantilla_nombre ?? "—"}</td>
      <td>
        <span className={`owner-cell ${esMio ? "yo" : ""}`}>
          <span className="avatar-mini">{iniciales}</span>
          {t.autor_nombre?.split(" ")[0]} {esMio && <span className="you-tag">tú</span>}
        </span>
      </td>
      <td><Confianza valor={t.confianza} /></td>
      <td><Estado estado={t.estado} /></td>
      <td style={{ color: "var(--text-3)" }}>{formatFecha(t.creada)}</td>
      <td style={{ textAlign: "right" }}>
        {confirmar ? (
          <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
            <span style={{ fontSize: "var(--fs-sm)", color: "var(--text-2)" }} title={nombreVisible}>
              ¿Eliminar «{recortar(nombreVisible, 24)}»?
            </span>
            <button className="btn" onClick={() => setConfirmar(false)} disabled={borrando}
              style={{ padding: "4px 10px" }}>No</button>
            <button className="btn" onClick={eliminar} disabled={borrando}
              style={{ padding: "4px 10px", background: "var(--danger-500)", color: "#fff", borderColor: "var(--danger-500)" }}>
              {borrando ? "…" : "Sí"}
            </button>
          </span>
        ) : (
          <span style={{ display: "inline-flex", gap: 6, alignItems: "center", justifyContent: "flex-end" }}>
            {(t.estado === "EN_REVISION" || t.estado === "MAPEO_PROPUESTO" || t.estado === "APROBADO") && (
              <button className="btn" onClick={() => navigate(`/transformar/${t.id}/mapeo`)}>
                <i className="ti ti-eye" /> Revisar
              </button>
            )}
            {t.estado === "GENERADO" && (
              <button className="btn btn-primary" onClick={() => navigate(`/transformar/${t.id}/mapeo`)}>
                <i className="ti ti-download" /> Ver
              </button>
            )}
            {puedeBorrar && (
              <button className="btn" title="Eliminar" onClick={() => setConfirmar(true)}
                style={{ padding: "7px 10px" }}>
                <i className="ti ti-trash" />
              </button>
            )}
          </span>
        )}
      </td>
    </tr>
  );
}

function Confianza({ valor }: { valor: number | null }) {
  if (valor === null) return <span style={{ color: "var(--text-3)", fontSize: "var(--fs-sm)" }}>—</span>;
  const clase = valor >= 85 ? "alta" : valor >= 60 ? "media" : "baja";
  return (
    <span className={`conf ${clase}`}>
      <span className="conf-bar"><span className="conf-fill" style={{ width: `${valor}%` }} /></span>
      <span className="conf-num">{valor}%</span>
    </span>
  );
}

function Estado({ estado }: { estado: string }) {
  const mapa: Record<string, { clase: string; icono: string; texto: string }> = {
    GENERADO: { clase: "done", icono: "ti ti-check", texto: "Completada" },
    APROBADO: { clase: "done", icono: "ti ti-check", texto: "Aprobada" },
    EN_REVISION: { clase: "review", icono: "ti ti-clock", texto: "En revisión" },
    MAPEO_PROPUESTO: { clase: "review", icono: "ti ti-clock", texto: "Mapeo propuesto" },
    LIMPIEZA: { clase: "processing", icono: "ti ti-loader-2", texto: "Procesando" },
    BORRADOR: { clase: "draft", icono: "ti ti-file", texto: "Borrador" },
    ERROR: { clase: "error", icono: "ti ti-alert-triangle", texto: "Error" },
  };
  const e = mapa[estado] ?? { clase: "draft", icono: "ti ti-file", texto: estado };
  return <span className={`pill ${e.clase}`}><i className={e.icono} /> {e.texto}</span>;
}

/**
 * Campo de fecha en formato dd/mm/aaaa. El input nativo muestra el formato del
 * idioma del navegador (a veces mm/dd/aaaa), así que se escribe como texto y
 * el botón de calendario abre el selector nativo oculto. `value` y `onChange`
 * trabajan en "AAAA-MM-DD" para comparar fácil.
 */
function FechaInput({ label, value, onChange, min, max }: {
  label: string;
  value: string;
  onChange: (iso: string) => void;
  min?: string;
  max?: string;
}) {
  const [texto, setTexto] = useState(isoADmy(value));
  const selectorRef = useRef<HTMLInputElement>(null);

  // Si el valor cambia desde fuera (ej. "Limpiar filtros"), se refleja en el texto.
  useEffect(() => {
    if (dmyAIso(texto) !== value) setTexto(isoADmy(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  function escribir(entrada: string) {
    const d = entrada.replace(/\D/g, "").slice(0, 8);
    const conBarras = [d.slice(0, 2), d.slice(2, 4), d.slice(4)].filter(Boolean).join("/");
    setTexto(conBarras);
    onChange(dmyAIso(conBarras));   // "" mientras esté incompleta o inválida
  }

  function abrirCalendario() {
    try { selectorRef.current?.showPicker(); } catch { selectorRef.current?.focus(); }
  }

  const invalida = texto.length === 10 && !dmyAIso(texto);

  return (
    <div className="filtro">
      <span>{label}</span>
      <div className="fecha-input">
        <input type="text" inputMode="numeric" placeholder="dd/mm/aaaa" aria-label={label}
          value={texto} onChange={(e) => escribir(e.target.value)}
          className={invalida ? "invalida" : ""} title={invalida ? "Fecha inválida" : undefined} />
        <button type="button" className="fecha-btn" onClick={abrirCalendario} title="Abrir calendario">
          <i className="ti ti-calendar" />
        </button>
        <input ref={selectorRef} type="date" className="fecha-selector" tabIndex={-1} aria-hidden
          value={value} min={min} max={max}
          onChange={(e) => { setTexto(isoADmy(e.target.value)); onChange(e.target.value); }} />
      </div>
    </div>
  );
}

/** "AAAA-MM-DD" → "dd/mm/aaaa". */
function isoADmy(iso: string) {
  const [a, m, d] = iso.split("-");
  return iso ? `${d}/${m}/${a}` : "";
}

/** "dd/mm/aaaa" → "AAAA-MM-DD", o "" si está incompleta o no existe (ej. 31/02). */
function dmyAIso(dmy: string) {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(dmy);
  if (!m) return "";
  const [, d, mes, a] = m;
  const f = new Date(Number(a), Number(mes) - 1, Number(d));
  if (f.getFullYear() !== Number(a) || f.getMonth() !== Number(mes) - 1 || f.getDate() !== Number(d)) {
    return "";
  }
  return `${a}-${mes}-${d}`;
}

/** Empresa de la transformación; si no se guardó, la de su plantilla. */
function empresaDe(t: Transformacion) {
  return t.mandante || t.plantilla_mandante || "";
}

/** Fecha local "AAAA-MM-DD" para comparar con los inputs de fecha. */
function fechaLocal(iso: string) {
  const d = new Date(iso);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function recortar(texto: string, max: number) {
  return texto.length > max ? `${texto.slice(0, max).trimEnd()}...` : texto;
}

function formatFecha(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("es-CL", { day: "2-digit", month: "short", year: "numeric" });
  } catch {
    return iso;
  }
}