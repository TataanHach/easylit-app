/**
 * Editor de campos de una plantilla, ORGANIZADO POR HOJAS.
 *
 * Arriba muestra las hojas del Excel (pestañas). Al elegir una hoja, se ven y
 * editan solo los campos de esa hoja. Cada campo nuevo se asocia a la hoja
 * activa (hoja_destino), y al generar el documento se escribe en esa hoja.
 *
 * Si el Excel tiene una sola hoja (o no se pudieron leer), funciona como antes:
 * una sola lista, sin pestañas.
 *
 * Guarda cada cambio contra el backend inmediatamente.
 */
import { useEffect, useRef, useState } from "react";
import { useAvisos } from "@/components/ui/Avisos";
import { describirError } from "@/lib/errores";
import { campoService, plantillaService } from "./plantillaService";
import type { Plantilla } from "@/types";
import { LIMITES, limpiarTexto } from "@/lib/limites";

const TIPOS = [
  { v: "TEXTO", t: "Texto" },
  { v: "NUMERO", t: "Número" },
  { v: "FECHA", t: "Fecha" },
  { v: "UNIDAD", t: "Unidad" },
];

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
  const avisos = useAvisos();
  const [campos, setCampos] = useState<any[]>([]);
  const [hojas, setHojas] = useState<string[]>([]);
  const [hojaActiva, setHojaActiva] = useState<string>("");
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    // Cargar campos y hojas en paralelo.
    Promise.all([
      campoService.listar(plantilla.id),
      plantillaService.hojas(plantilla.id).catch(() => ({ hojas: [] })),
    ])
      .then(([listaCampos, resp]) => {
        setCampos(listaCampos);
        const hs: string[] = resp?.hojas ?? [];
        setHojas(hs);
        // Hoja activa inicial: la primera del Excel, o "" si no hay hojas.
        setHojaActiva(hs.length > 0 ? hs[0] : "");
      })
      .finally(() => setCargando(false));
  }, [plantilla.id]);

  // Campos de la hoja activa. Si no hay hojas (Excel de 1 hoja o ilegible),
  // mostramos todos (comportamiento antiguo).
  const hayHojas = hojas.length > 1;
  const camposVisibles = hayHojas
    ? campos.filter((c) => (c.hoja_destino || "") === hojaActiva)
    : campos;

  async function agregar() {
    setGuardando(true);
    try {
      const nuevo = await campoService.crear({
        plantilla: plantilla.id, nombre: "Nuevo_Campo", tipo: "TEXTO",
        etiqueta_busqueda: "", orden: camposVisibles.length,
        // Asociar el campo a la hoja activa (si hay hojas).
        hoja_destino: hayHojas ? hojaActiva : "",
      });
      setCampos([...campos, nuevo]);
    } catch (e) {
      avisos.error(describirError(e, "añadir el campo"));
    } finally { setGuardando(false); }
  }

  // Último valor guardado de cada campo, para volver a él si un cambio falla.
  const guardados = useRef<Record<string, any>>({});
  useEffect(() => {
    campos.forEach((c) => { guardados.current[c.id] ??= c; });
  }, [campos]);

  async function actualizar(id: string, cambios: any) {
    setCampos((lista) => lista.map((c) => (c.id === id ? { ...c, ...cambios } : c)));
    try {
      await campoService.editar(id, cambios);
      guardados.current[id] = { ...guardados.current[id], ...cambios };
    } catch (e) {
      const anterior = guardados.current[id];
      if (anterior) setCampos((lista) => lista.map((c) => (c.id === id ? anterior : c)));
      avisos.error(describirError(e, "guardar el cambio del campo"));
    }
  }

  function guardarNombre(id: string, valor: string) {
    const nombre = limpiarTexto(valor);
    if (!nombre) {
      // Sin nombre el campo no se puede identificar: se vuelve al anterior.
      const anterior = guardados.current[id];
      if (anterior) setCampos((lista) => lista.map((c) => (c.id === id ? { ...c, nombre: anterior.nombre } : c)));
      avisos.error("El campo necesita un nombre", "No se puede dejar vacío. Se restauró el nombre anterior.");
      return;
    }
    actualizar(id, { nombre });
  }

  async function quitar(id: string) {
    const lista = campos;
    setCampos(campos.filter((c) => c.id !== id));
    try {
      await campoService.eliminar(id);
    } catch (e) {
      setCampos(lista);
      avisos.error(describirError(e, "quitar el campo"));
    }
  }

    const esNumerico = (tipo: string) => tipo === "NUMERO";


  // Cuántos campos tiene cada hoja, para mostrarlo en las pestañas.
  const contarHoja = (h: string) => campos.filter((c) => (c.hoja_destino || "") === h).length;

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
            a campos numéricos o de moneda. Los cambios se guardan al momento.
          </p>

          {cargando ? (
            <p style={{ color: "var(--text-3)" }}><i className="ti ti-loader-2" style={{ marginRight: 6 }} />Cargando…</p>
          ) : (
            <>
              {/* Pestañas por hoja (solo si el Excel tiene varias hojas) */}
              {hayHojas && (
                <div className="hoja-tabs">
                  {hojas.map((h) => (
                    <button
                      key={h}
                      className={`hoja-tab ${h === hojaActiva ? "activa" : ""}`}
                      onClick={() => setHojaActiva(h)}
                    >
                      <i className="ti ti-file-spreadsheet" /> {h}
                      <span className="hoja-tab-count">{contarHoja(h)}</span>
                    </button>
                  ))}
                </div>
              )}

              <div className="campo-fila head">
                <span>Nombre</span>
                <span>Tipo</span>
                <span>Formato</span>
                <span>Etiqueta de búsqueda</span>
                <span></span>
              </div>
              {camposVisibles.map((c) => (
                <div className="campo-fila" key={c.id}>
                  <input value={c.nombre} maxLength={LIMITES.nombreCampo}
                    onChange={(e) => setCampos(campos.map((x) => x.id === c.id ? { ...x, nombre: e.target.value } : x))}
                    onBlur={(e) => guardarNombre(c.id, e.target.value)} />

                  <select value={c.tipo} onChange={(e) => actualizar(c.id, { tipo: e.target.value })}>
                    {TIPOS.map((t) => <option key={t.v} value={t.v}>{t.t}</option>)}
                  </select>

                  <select
                    value={c.formato_numero ?? "NINGUNO"}
                    disabled={!esNumerico(c.tipo)}
                    title={esNumerico(c.tipo) ? "Formato del número" : "Solo para campos Número o Moneda"}
                    onChange={(e) => actualizar(c.id, { formato_numero: e.target.value })}
                  >
                    {FORMATOS.map((f) => <option key={f.v} value={f.v}>{f.t}</option>)}
                  </select>

                  <input value={c.etiqueta_busqueda ?? ""} placeholder="Ej. RUT" maxLength={LIMITES.etiquetaBusqueda}
                    onChange={(e) => setCampos(campos.map((x) => x.id === c.id ? { ...x, etiqueta_busqueda: e.target.value } : x))}
                    onBlur={(e) => actualizar(c.id, { etiqueta_busqueda: limpiarTexto(e.target.value) })} />

                  <button className="campo-del" title="Quitar" onClick={() => quitar(c.id)}>
                    <i className="ti ti-trash" />
                  </button>
                </div>
              ))}
              {camposVisibles.length === 0 && (
                <p style={{ color: "var(--text-3)", padding: "16px 0", fontSize: "var(--fs-md)" }}>
                  {hayHojas
                    ? `La hoja "${hojaActiva}" aún no tiene campos. Añade el primero abajo.`
                    : "Aún no hay campos. Añade el primero abajo."}
                </p>
              )}
              <button className="add-campo" onClick={agregar} disabled={guardando}>
                <i className="ti ti-plus" /> Añadir campo{hayHojas ? ` a "${hojaActiva}"` : ""}
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