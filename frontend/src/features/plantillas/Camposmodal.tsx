/**
 * Editor de campos de una plantilla.
 *
 * Permite añadir, editar y quitar los campos que definen qué datos espera la
 * plantilla, dónde escribirlos (etiqueta de búsqueda) y con qué FORMATO numérico
 * (pesos, porcentaje, UF...). Sin campos, una plantilla no puede mapear ni
 * generar bien.
 *
 * Guarda cada cambio contra el backend inmediatamente (crear/editar/borrar).
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

// Opciones de formato numérico. Coinciden con las del modelo en el backend.
const FORMATOS = [
  { v: "NINGUNO", t: "Sin formato" },
  { v: "ENTERO", t: "Número entero" },
  { v: "DECIMAL", t: "Decimal" },
  { v: "PESOS", t: "Pesos $" },
  { v: "PESOS_DEC", t: "Pesos con decimales" },
  { v: "PORCENTAJE", t: "Porcentaje %" },
  { v: "UF", t: "UF" },
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
    setCampos(campos.map((c) => (c.id === id ? { ...c, ...cambios } : c)));
    await campoService.editar(id, cambios);
  }

  async function quitar(id: string) {
    setCampos(campos.filter((c) => c.id !== id));
    await campoService.eliminar(id);
  }

  // ¿El campo es numérico? Solo entonces tiene sentido elegir formato.
  const esNumerico = (tipo: string) => tipo === "NUMERO" || tipo === "MONEDA";

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
            el texto de la casilla en tu formulario (ej. "RUT"). El <strong>formato</strong> aplica solo
            a campos numéricos o de moneda (pesos, porcentaje, UF). Los cambios se guardan al momento.
          </p>

          {cargando ? (
            <p style={{ color: "var(--text-3)" }}>Cargando…</p>
          ) : (
            <>
              <div className="campo-fila head">
                <span>Nombre</span>
                <span>Tipo</span>
                <span>Formato</span>
                <span>Etiqueta de búsqueda</span>
                <span></span>
              </div>
              {campos.map((c) => (
                <div className="campo-fila" key={c.id}>
                  <input value={c.nombre}
                    onChange={(e) => setCampos(campos.map((x) => x.id === c.id ? { ...x, nombre: e.target.value } : x))}
                    onBlur={(e) => actualizar(c.id, { nombre: e.target.value })} />

                  <select value={c.tipo} onChange={(e) => actualizar(c.id, { tipo: e.target.value })}>
                    {TIPOS.map((t) => <option key={t.v} value={t.v}>{t.t}</option>)}
                  </select>

                  {/* Formato: solo activo si el campo es numérico o moneda */}
                  <select
                    value={c.formato_numero ?? "NINGUNO"}
                    disabled={!esNumerico(c.tipo)}
                    title={esNumerico(c.tipo) ? "Formato del número" : "Solo para campos Número o Moneda"}
                    onChange={(e) => actualizar(c.id, { formato_numero: e.target.value })}
                  >
                    {FORMATOS.map((f) => <option key={f.v} value={f.v}>{f.t}</option>)}
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