/**
 * Biblioteca de plantillas.
 *
 * Muestra las plantillas como tarjetas y permite crear, editar y eliminar desde
 * la propia app (sin ir al admin de Django). La edición de CAMPOS de la
 * plantilla sigue en el admin por ahora; esto cubre crear/editar/borrar la
 * plantilla en sí.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { plantillaService } from "./plantillaService";
import PlantillaModal from "./PlantillaModal";
import ConfirmarEliminar from "./ConfirmarEliminar";
import CamposModal from "./CamposModal";
import type { Plantilla } from "@/types";
import "./plantillas.css";

export default function PlantillasPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["plantillas"],
    queryFn: plantillaService.listar,
  });

  const [modalCrear, setModalCrear] = useState(false);
  const [editando, setEditando] = useState<Plantilla | null>(null);
  const [eliminando, setEliminando] = useState<Plantilla | null>(null);
  const [editandoCampos, setEditandoCampos] = useState<Plantilla | null>(null);

  function trasGuardar() {
    setModalCrear(false);
    setEditando(null);
    refetch();
  }
  function trasEliminar() {
    setEliminando(null);
    refetch();
  }

  return (
    <>
      <div className="pl-header">
        <div>
          <h1>Biblioteca de plantillas</h1>
          <p>Formatos de mandantes que puedes crear, editar y reutilizar.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setModalCrear(true)}>
          <i className="ti ti-plus" /> Nueva plantilla
        </button>
      </div>

      {isLoading && (
        <div className="pl-estado"><i className="ti ti-loader-2" /><p style={{ marginTop: 8 }}>Cargando…</p></div>
      )}
      {isError && (
        <div className="pl-estado">
          <i className="ti ti-alert-circle" style={{ color: "var(--danger-500)" }} />
          <h3>No se pudo cargar</h3><p>Revisa que el backend esté corriendo.</p>
        </div>
      )}

      {data && data.length === 0 && (
        <div className="pl-estado">
          <i className="ti ti-template" />
          <h3>Aún no hay plantillas</h3>
          <p>Crea tu primera plantilla con el botón de arriba.</p>
        </div>
      )}

      {data && data.length > 0 && (
        <>
          <p style={{ fontSize: "var(--fs-md)", color: "var(--text-3)", marginBottom: 16 }}>
            {data.length} plantilla{data.length !== 1 ? "s" : ""}
          </p>
          <div className="pl-grid">
            {data.map((p) => (
              <Tarjeta key={p.id} p={p}
                onUsar={() => navigate("/transformar")}
                onEditar={() => setEditando(p)}
                onCampos={() => setEditandoCampos(p)}
                onEliminar={() => setEliminando(p)} />
            ))}
          </div>
        </>
      )}

      {(modalCrear || editando) && (
        <PlantillaModal
          plantilla={editando}
          onCerrar={() => { setModalCrear(false); setEditando(null); }}
          onGuardado={trasGuardar} />
      )}
      {eliminando && (
        <ConfirmarEliminar plantilla={eliminando}
          onCerrar={() => setEliminando(null)} onEliminado={trasEliminar} />
      )}
      {editandoCampos && (
        <CamposModal plantilla={editandoCampos}
          onCerrar={() => { setEditandoCampos(null); refetch(); }} />
      )}
    </>
  );
}

function Tarjeta({ p, onUsar, onEditar, onCampos, onEliminar }: {
  p: Plantilla; onUsar: () => void; onEditar: () => void; onCampos: () => void; onEliminar: () => void;
}) {
  const fmt = (p.formato ?? "xlsx").toLowerCase();
  return (
    <div className="pl-card">
      <div className={`pl-preview ${fmt}`}>
        <span className={`pl-badge ${fmt}`}>{p.formato}</span>
        <div className="pl-doc-mock">
          <span className="pl-ln t" />
          <span className="pl-ln a" /><span className="pl-ln b" /><span className="pl-ln c" /><span className="pl-ln a" />
        </div>
      </div>
      <div className="pl-body">
        <p className="pl-name">{p.nombre}</p>
        <p className="pl-org">
          <i className="ti ti-building" /> {p.mandante || "Sin mandante"}{p.sector ? ` · ${p.sector}` : ""}
        </p>
        <div className="pl-tags">
          <span className="pl-tag">{p.total_campos} campo{p.total_campos !== 1 ? "s" : ""}</span>
          {p.total_campos === 0 && <span className="pl-tag" style={{ color: "var(--warn-700)", borderColor: "var(--warn-100)", background: "var(--warn-50)" }}>Sin campos</span>}
        </div>
        <div className="pl-foot">
          <div className="pl-acciones">
            <button className="pl-icon-btn" title="Usar" onClick={onUsar}><i className="ti ti-player-play" /></button>
            <button className="pl-icon-btn" title="Editar campos" onClick={onCampos}><i className="ti ti-list-details" /></button>
            <button className="pl-icon-btn" title="Editar datos" onClick={onEditar}><i className="ti ti-edit" /></button>
            <button className="pl-icon-btn danger" title="Eliminar" onClick={onEliminar}><i className="ti ti-trash" /></button>
          </div>
          <span className="pl-usos">{p.usos}</span>
        </div>
      </div>
    </div>
  );
}