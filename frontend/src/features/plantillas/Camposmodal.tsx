/**
 * Editor de campos de una plantilla.
 *
 * Permite añadir, editar y quitar los campos que definen qué datos espera la
 * plantilla y dónde escribirlos (la "etiqueta de búsqueda"). Sin campos, una
 * plantilla no puede mapear ni generar bien.
 *
 * Guarda cada cambio contra el backend inmediatamente (crear/editar/borrar),
 * así el usuario ve el estado real siempre.
 */
import { useEffect, useState } from "react";
import { campoService } from "./plantillaService";
import type { Plantilla } from "@/types";

const TIPOS = [
  { v: "TEXTO", t: "Texto" },
  { v: "NUMERO", t: "Número" },
  { v: "MONEDA", t: "Moneda" },
  { v: "FECHA", t: "Fecha" },
  { v: "UNIDAD", t: "Unidad" },
];

interface Props { plantilla: Plantilla; onCerrar: () => void; }

export default function CamposModal({ plantilla, onCerrar }: Props) {
  const [campos, setCampos] = useState<any[]>([]);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    campoService.listar(plantilla.id)
      .then((d) => setCampos(d))
      .finally(() => setCargando(false));
  }, [plantilla.id]);

  async function agregar() {
    setGuardando(true);
    try {
      const nuevo = await campoService.crear({
        plantilla: plantilla.id, nombre: "Nuevo_Campo", tipo: "TEXTO",
        etiqueta_busqueda: "", orden: campos.length,
      });
      setCampos([...campos, nuevo]);
    } finally { setGuardando(false); }
  }

  async function actualizar(id: string, cambios: any) {
    // Optimista: actualizar en pantalla, luego guardar.
    setCampos(campos.map((c) => (c.id === id ? { ...c, ...cambios } : c)));
    await campoService.editar(id, cambios);
  }

  async function quitar(id: string) {
    setCampos(campos.filter((c) => c.id !== id));
    await campoService.eliminar(id);
  }

  return (
    <div className="modal-overlay" onClick={onCerrar}>
      <div className="modal campos-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>Campos de "{plantilla.nombre}"</h2>
          <button className="modal-close" onClick={onCerrar}><i className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          <p className="campos-hint">
            Cada campo es un dato que la plantilla espera. La <strong>etiqueta de búsqueda</strong> es
            el texto exacto de la casilla en tu formulario (ej. "RUT" o "Razón Social"), para saber
            dónde escribir el valor. Los cambios se guardan al momento.
          </p>

          {cargando ? (
            <p style={{ color: "var(--text-3)" }}>Cargando…</p>
          ) : (
            <>
              <div className="campo-fila head">
                <span>Nombre</span><span>Tipo</span><span>Etiqueta de búsqueda</span><span></span>
              </div>
              {campos.map((c) => (
                <div className="campo-fila" key={c.id}>
                  <input value={c.nombre}
                    onChange={(e) => setCampos(campos.map((x) => x.id === c.id ? { ...x, nombre: e.target.value } : x))}
                    onBlur={(e) => actualizar(c.id, { nombre: e.target.value })} />
                  <select value={c.tipo} onChange={(e) => actualizar(c.id, { tipo: e.target.value })}>
                    {TIPOS.map((t) => <option key={t.v} value={t.v}>{t.t}</option>)}
                  </select>
                  <input value={c.etiqueta_busqueda ?? ""} placeholder="Ej. RUT"
                    onChange={(e) => setCampos(campos.map((x) => x.id === c.id ? { ...x, etiqueta_busqueda: e.target.value } : x))}
                    onBlur={(e) => actualizar(c.id, { etiqueta_busqueda: e.target.value })} />
                  <button className="campo-del" title="Quitar" onClick={() => quitar(c.id)}>
                    <i className="ti ti-trash" />
                  </button>
                </div>
              ))}
              {campos.length === 0 && (
                <p style={{ color: "var(--text-3)", padding: "16px 0", fontSize: "var(--fs-md)" }}>
                  Aún no hay campos. Añade el primero abajo.
                </p>
              )}
              <button className="add-campo" onClick={agregar} disabled={guardando}>
                <i className="ti ti-plus" /> Añadir campo
              </button>
            </>
          )}
        </div>
        <div className="modal-foot">
          <button className="btn btn-primary" onClick={onCerrar}>Listo</button>
        </div>
      </div>
    </div>
  );
}