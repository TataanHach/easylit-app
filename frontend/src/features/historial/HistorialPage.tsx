/**
 * Pantalla de historial.
 *
 * Muestra las transformaciones en una tabla, con el filtro Mías / De mi equipo /
 * Todas. Usa React Query para pedir los datos al backend y manejar los estados
 * de carga y error sin código manual. Cada tab cambia el parámetro `alcance` y
 * React Query vuelve a pedir (con caché por alcance).
 */
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";
import { transformacionService, type Alcance } from "./historialService";
import type { Transformacion } from "@/types";
import "./historial.css";

const TABS: { clave: Alcance; label: string; icono: string }[] = [
  { clave: "mine", label: "Mías", icono: "ti ti-user" },
  { clave: "team", label: "De mi equipo", icono: "ti ti-users" },
  { clave: "all", label: "Todas", icono: "ti ti-building" },
];

export default function HistorialPage() {
  const { usuario } = useAuth();
  const [alcance, setAlcance] = useState<Alcance>("mine");

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
            {data && <span className="panel-count">{data.length} resultado{data.length !== 1 ? "s" : ""}</span>}
          </div>
        </div>

        {isLoading && (
          <div className="estado-caja">
            <i className="ti ti-loader-2" /><p style={{ marginTop: 8 }}>Cargando…</p>
          </div>
        )}

        {isError && (
          <div className="estado-caja">
            <i className="ti ti-alert-circle" style={{ color: "var(--danger-500)" }} />
            <h3>No se pudo cargar</h3>
            <p>Revisa que el backend esté corriendo.</p>
          </div>
        )}

        {data && data.length === 0 && (
          <div className="estado-caja">
            <i className="ti ti-folder-open" />
            <h3>Nada por aquí todavía</h3>
            <p>No hay transformaciones con este filtro.</p>
          </div>
        )}

        {data && data.length > 0 && (
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
                {data.map((t) => (
                  <Fila key={t.id} t={t} esMio={t.autor === usuario?.id} />
                ))}
              </tbody>
            </table>
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
  const [confirmar, setConfirmar] = useState(false);
  const [borrando, setBorrando] = useState(false);

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
    } catch {
      alert("No se pudo eliminar. Puede que no tengas permiso.");
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
            <p className="doc-name">{t.nombre_origen}</p>
            {t.mandante && <p style={{ fontSize: "var(--fs-sm)", color: "var(--text-3)" }}>{t.mandante}</p>}
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
            <span style={{ fontSize: "var(--fs-sm)", color: "var(--text-2)" }}>¿Eliminar?</span>
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

function formatFecha(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("es-CL", { day: "2-digit", month: "short", year: "numeric" });
  } catch {
    return iso;
  }
}