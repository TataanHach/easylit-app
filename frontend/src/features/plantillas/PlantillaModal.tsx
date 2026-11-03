/**
 * Modal para crear o editar una plantilla.
 *
 * En modo crear: pide nombre, mandante (obligatorio), sector y archivo.
 * En modo editar: permite cambiar nombre/mandante/sector (no el archivo, para
 * no invalidar transformaciones que ya lo usan).
 *
 * El mandante se guarda en mayúsculas (el backend lo normaliza igual), para que
 * «Codelco» y «CODELCO» no aparezcan como dos empresas distintas.
 */
import { FormEvent, useEffect, useState } from "react";
import { plantillaService } from "./plantillaService";
import { LIMITES, limpiarTexto } from "@/lib/limites";
import { ACEPTA_ARCHIVO, problemaArchivo, useArrastrar } from "@/lib/archivos";
import { describirError } from "@/lib/errores";
import AyudaPlantilla from "./AyudaPlantilla";
import type { Plantilla } from "@/types";

/** Igual que normalizar_mandante del backend: mayúsculas y sin espacios de más. */
const mandanteNormal = (s: string) => limpiarTexto(s).replace(/\s+/g, " ").toLocaleUpperCase("es-CL");

interface Props {
  plantilla?: Plantilla | null; // si viene, es edición
  onCerrar: () => void;
  /** `creada` viene solo al crear: la plantilla nueva, para abrir sus campos. */
  onGuardado: (nombre: string, creada?: Plantilla) => void;
}

export default function PlantillaModal({ plantilla, onCerrar, onGuardado }: Props) {
  const esEdicion = !!plantilla;
  const [nombre, setNombre] = useState(plantilla?.nombre ?? "");
  const [mandante, setMandante] = useState(plantilla?.mandante ?? "");
  const [sector, setSector] = useState(plantilla?.sector ?? "");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [verAyuda, setVerAyuda] = useState(false);

  // Se revisa al elegirlo: así el usuario no espera la subida para saber que no sirve.
  async function elegirArchivo(f: File | null) {
    setError("");
    const problema = f ? await problemaArchivo(f) : "";
    if (problema) { setError(problema); setArchivo(null); return; }
    setArchivo(f);
  }
  const arrastre = useArrastrar((f) => elegirArchivo(f));

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setError("");
    const datos = {
      nombre: limpiarTexto(nombre), mandante: mandanteNormal(mandante), sector: limpiarTexto(sector),
    };
    setNombre(datos.nombre); setMandante(datos.mandante); setSector(datos.sector);
    if (!datos.nombre) { setError("Falta el nombre de la plantilla. Escríbelo para poder guardarla."); return; }
    if (!datos.mandante) { setError("Falta el mandante. Escribe para quién es este formato (ej. MINEDUC, Codelco)."); return; }
    if (!esEdicion && !archivo) { setError("Falta el archivo del formato. Sube el Excel del mandante para crear la plantilla."); return; }
    setGuardando(true);
    let creada: Plantilla | undefined;
    try {
      if (esEdicion) {
        await plantillaService.editar(plantilla!.id, datos);
      } else {
        const formato = archivo!.name.toLowerCase().endsWith(".csv") ? "CSV" : "XLSX";
        creada = await plantillaService.crear({ ...datos, formato, archivo: archivo! });
      }
    } catch (e) {
      const { titulo, detalle } = describirError(e, "guardar la plantilla");
      setError(`${titulo}. ${detalle}`);
      setGuardando(false);
      return;
    }
    // Fuera del try: la plantilla ya quedó guardada, así que un fallo al cerrar
    // el modal no debe decir "No se pudo guardar" (eso llevaba a crearla dos veces).
    onGuardado(datos.nombre, creada);
  }

  // Escape cierra, como la X (salvo mientras se guarda o con la ayuda abierta encima).
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape" && !guardando && !verAyuda) onCerrar(); };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [guardando, verAyuda, onCerrar]);

  return (
    <div className="modal-overlay">
      {verAyuda && <AyudaPlantilla onCerrar={() => setVerAyuda(false)} />}
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="plantilla-modal-titulo">
        <div className="modal-head">
          <h2 id="plantilla-modal-titulo">{esEdicion ? "Editar plantilla" : "Nueva plantilla"}</h2>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button type="button" className="ayuda-btn" onClick={() => setVerAyuda(true)}
              title="¿Cómo subir una plantilla?" aria-label="Ayuda: cómo subir una plantilla">
              <i aria-hidden="true" className="ti ti-help" /> Ayuda
            </button>
            <button className="modal-close" onClick={onCerrar} aria-label="Cerrar"><i aria-hidden="true" className="ti ti-x" /></button>
          </div>
        </div>
        <form onSubmit={guardar} noValidate>
          <div className="modal-body">
            {error && <div className="modal-error">{error}</div>}

            <div className="mfield">
              <label>Nombre *</label>
              <input value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={LIMITES.nombrePlantilla}
                onBlur={(e) => setNombre(limpiarTexto(e.target.value))}
                placeholder="Ej. Formulario Identificación MINEDUC" autoFocus />
            </div>
            <div className="mfield">
              <label htmlFor="plantilla-mandante">Mandante *</label>
              {/* Se ve en mayúsculas mientras escribe (CSS) y se guarda así al salir del campo. */}
              <input id="plantilla-mandante" className="mayusculas" value={mandante} maxLength={LIMITES.mandante}
                onChange={(e) => setMandante(e.target.value)}
                onBlur={(e) => setMandante(mandanteNormal(e.target.value))}
                placeholder="Ej. MINEDUC, Codelco…" />
              <p className="mfield-ayuda">Se guarda en mayúsculas, así cada empresa aparece una sola vez en los filtros.</p>
            </div>
            <div className="mfield">
              <label>Sector</label>
              <input value={sector} onChange={(e) => setSector(e.target.value)} maxLength={LIMITES.sector}
                onBlur={(e) => setSector(limpiarTexto(e.target.value))}
                placeholder="Ej. Educación, Minería…" />
            </div>

            {!esEdicion && (
              <div className="mfield">
                <label>Archivo del formato *</label>
                <label className={`file-drop ${archivo ? "tiene" : ""} ${arrastre.encima ? "arrastrando" : ""}`}
                  {...arrastre.props}>
                  <input type="file" accept={ACEPTA_ARCHIVO} className="solo-lector"
                    onChange={(e) => { elegirArchivo(e.target.files?.[0] ?? null); e.target.value = ""; }} />
                  {arrastre.encima
                    ? <><i aria-hidden="true" className="ti ti-upload" /> Suelta el archivo aquí</>
                    : archivo
                      ? <><i aria-hidden="true" className="ti ti-file-check" /> {archivo.name}</>
                      : <><i aria-hidden="true" className="ti ti-upload" /> Arrastra el archivo aquí o haz clic para elegirlo</>}
                </label>
                <p className="mfield-ayuda">Formato .xlsx (Excel) o .csv. Usa el archivo original del mandante, sin cambios.</p>
              </div>
            )}

            {esEdicion && (
              <p style={{ fontSize: "var(--fs-sm)", color: "var(--text-3)" }}>
                Para cambiar el archivo o los campos, hazlo desde el panel de administración.
              </p>
            )}
          </div>
          <div className="modal-foot">
            <button type="button" className="btn" onClick={onCerrar}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={guardando}>
              {guardando ? "Guardando…" : esEdicion ? "Guardar cambios" : "Crear y agregar campos"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}