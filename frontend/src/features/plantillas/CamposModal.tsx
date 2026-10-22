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
import { campoService, plantillaService, type RevisionHojas } from "./plantillaService";
import ResultadoModal, { type Resultado } from "@/components/ui/ResultadoModal";
import ConfirmarModal from "@/components/ui/ConfirmarModal";
import AyudaCampos from "./AyudaCampos";
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
  const [revision, setRevision] = useState<RevisionHojas | null>(null);
  const [hojaActiva, setHojaActiva] = useState<string>("");
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [revisando, setRevisando] = useState(false);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  // Campo que se pidió eliminar: espera la confirmación antes de borrarlo.
  const [porEliminar, setPorEliminar] = useState<any | null>(null);
  const [verAyuda, setVerAyuda] = useState(false);

  useEffect(() => {
    // Cargar campos y hojas en paralelo.
    Promise.all([
      campoService.listar(plantilla.id),
      plantillaService.hojas(plantilla.id).catch(() => null),
    ])
      .then(([listaCampos, resp]) => {
        setCampos(listaCampos);
        setRevision(resp);
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

  // Nombre libre para un campo nuevo: Nuevo_Campo, Nuevo_Campo_2, … (el
  // backend no acepta dos campos con el mismo nombre en una plantilla).
  function nombreLibre() {
    const usados = new Set(campos.map((c) => String(c.nombre).toLowerCase()));
    let nombre = "Nuevo_Campo";
    for (let i = 2; usados.has(nombre.toLowerCase()); i++) nombre = `Nuevo_Campo_${i}`;
    return nombre;
  }

  // Tras cada cambio se vuelve a revisar la plantilla: así el aviso de un campo
  // (ej. "no se encontró la etiqueta") aparece o desaparece al momento.
  function revisar() {
    plantillaService.hojas(plantilla.id).then(setRevision).catch(() => {});
  }
  const infoHoja = (h: string) => revision?.detalle.find((d) => d.nombre === h);
  const esTabla = (h: string) => infoHoja(h)?.tipo === "tabla";

  const [cambiandoTipo, setCambiandoTipo] = useState(false);
  async function cambiarTipoHoja(hoja: string, tipo: "AUTO" | "TABLA" | "FORMULARIO") {
    setCambiandoTipo(true);
    try {
      const r = await plantillaService.tipoHoja(plantilla.id, hoja, tipo);
      setRevision(r);
      const nuevo = r.detalle.find((d) => d.nombre === hoja)?.tipo;
      avisos.exito(
        "Tipo de hoja actualizado",
        tipo === "AUTO"
          ? `«${hoja}» vuelve a detectarse sola: hoy se ve como ${nuevo === "tabla" ? "tabla" : "formulario"}.`
          : `«${hoja}» se tratará siempre como ${tipo === "TABLA" ? "tabla (se llena automáticamente con la tabla del origen)" : "formulario (necesita campos)"}.`
      );
    } catch (e) {
      avisos.error(describirError(e, "cambiar el tipo de la hoja"));
    } finally {
      setCambiandoTipo(false);
    }
  }
  const conProblema = (h: string) =>
    campos.some((c) => (c.hoja_destino || "") === h && revision?.problemas[c.id]);

  /**
   * "Listo": revisa la plantilla completa y muestra el resultado en una
   * ventana: ✓ todo correcto, ⚠ campos con problemas (cuáles, en qué hoja y por
   * qué) o ✗ la plantilla no se pudo revisar.
   */
  async function terminar() {
    setRevisando(true);
    let r: RevisionHojas;
    try {
      r = await plantillaService.hojas(plantilla.id);
      setRevision(r);
    } catch (e) {
      const { detalle } = describirError(e, "revisar la plantilla");
      setResultado({ estado: "error", titulo: "No se pudo revisar la plantilla", mensaje: detalle });
      return;
    } finally {
      setRevisando(false);
    }

    if (r.error) {
      setResultado({ estado: "error", titulo: "No se pudo leer el Excel de la plantilla", mensaje: r.error });
      return;
    }
    const tablas = r.detalle.filter((h) => h.tipo === "tabla");
    const formularios = r.detalle.filter((h) => h.tipo === "formulario");
    if (campos.length === 0 && tablas.length === 0) {
      setResultado({
        estado: "error",
        titulo: "La plantilla no tiene nada que llenar",
        mensaje: "No tiene campos y en su Excel no se reconoció ninguna tabla, así que el documento "
          + "saldría igual al original. Agrega un campo por cada casilla que deba llenarse.",
      });
      return;
    }

    const cifras = [
      { etiqueta: campos.length === 1 ? "campo" : "campos", valor: campos.length },
      { etiqueta: formularios.length === 1 ? "hoja formulario" : "hojas formulario", valor: formularios.length },
      { etiqueta: tablas.length === 1 ? "hoja tabla" : "hojas tabla", valor: tablas.length },
    ];

    // Problemas agrupados por hoja, en el orden del Excel. Un campo sin hoja va
    // a la primera (la activa del Excel), igual que al generar.
    const hojaDe = (c: any) => c.hoja_destino || r.hojas[0];
    const grupos = r.detalle
      .map((h) => {
        const items = campos
          .filter((c) => hojaDe(c) === h.nombre && r.problemas[c.id])
          .map((c) => `«${c.nombre}»: ${r.problemas[c.id]}`);
        if (h.tipo === "formulario" && !campos.some((c) => hojaDe(c) === h.nombre)) {
          items.push("No tiene campos, así que no se llenará nada en ella. Si es una portada o "
            + "instrucciones, puedes ignorar este aviso.");
        }
        return { titulo: `Hoja «${h.nombre}»`, items };
      })
      .filter((g) => g.items.length > 0);
    // Campos cuya hoja ya no existe en el Excel.
    const huerfanos = campos.filter((c) => r.problemas[c.id] && c.hoja_destino && !r.hojas.includes(c.hoja_destino));
    if (huerfanos.length) {
      grupos.push({ titulo: "Hojas que ya no existen", items: huerfanos.map((c) => `«${c.nombre}»: ${r.problemas[c.id]}`) });
    }

    if (grupos.length > 0) {
      const malos = campos.filter((c) => r.problemas[c.id]).length;
      setResultado({
        estado: "advertencia",
        titulo: "La plantilla tiene cosas por revisar",
        mensaje: malos > 0
          ? `${campos.length - malos} de ${campos.length} campos están bien. Los de abajo no se podrán llenar al transformar:`
          : "Todos los campos encontraron su casilla, pero revisa lo siguiente:",
        cifras,
        grupos,
      });
      return;
    }

    const textoTablas = tablas.length
      ? ` ${tablas.length === 1 ? "La hoja" : "Las hojas"} ${tablas.map((h) => `«${h.nombre}»`).join(", ")} `
        + `${tablas.length === 1 ? "es una tabla y se llenará automáticamente" : "son tablas y se llenarán automáticamente"}.`
      : "";
    setResultado({
      estado: "exito",
      titulo: "Todo está correcto",
      mensaje: (campos.length
        ? `Los ${campos.length} campos encontraron su casilla en el Excel.`
        : "La plantilla no tiene campos de formulario.") + textoTablas,
      cifras,
    });
  }

  async function agregar() {
    setGuardando(true);
    try {
      const nuevo = await campoService.crear({
        plantilla: plantilla.id, nombre: nombreLibre(), tipo: "TEXTO",
        etiqueta_busqueda: "", orden: camposVisibles.length,
        // Asociar el campo a la hoja activa (si hay hojas).
        hoja_destino: hayHojas ? hojaActiva : "",
      });
      setCampos([...campos, nuevo]);
      revisar();
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
      revisar();
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
    const nombre = campos.find((c) => c.id === id)?.nombre ?? "";
    setCampos(campos.filter((c) => c.id !== id));
    try {
      await campoService.eliminar(id);
      revisar();
      avisos.exito("Campo eliminado", `«${nombre}» se quitó de la plantilla.`);
    } catch (e) {
      setCampos(lista);
      avisos.error(describirError(e, "quitar el campo"));
    }
  }

    const esNumerico = (tipo: string) => tipo === "NUMERO";


  // Cuántos campos tiene cada hoja, para mostrarlo en las pestañas.
  const contarHoja = (h: string) => campos.filter((c) => (c.hoja_destino || "") === h).length;

  // Escape cierra, salvo que haya otra ventana encima (ayuda, confirmar o resultado).
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !verAyuda && !porEliminar && !resultado) onCerrar();
    };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [verAyuda, porEliminar, resultado, onCerrar]);

  return (
    <div className="modal-overlay">
      <div className="modal campos-modal" role="dialog" aria-modal="true" aria-labelledby="campos-modal-titulo">
        <div className="modal-head">
          <h2 id="campos-modal-titulo">Campos de «{plantilla.nombre}»</h2>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button className="ayuda-btn" onClick={() => setVerAyuda(true)} title="¿Cómo funcionan los campos?"
              aria-label="Ayuda: cómo funcionan los campos">
              <i aria-hidden="true" className="ti ti-help" /> ?
            </button>
            <button className="modal-close" onClick={onCerrar} aria-label="Cerrar"><i aria-hidden="true" className="ti ti-x" /></button>
          </div>
        </div>
        <div className="modal-body">
          <p className="campos-hint">
            Cada campo es un dato que la plantilla espera. La <strong>etiqueta de búsqueda</strong> es
            el texto de la casilla en tu formulario (ej. "RUT"). El <strong>formato</strong> aplica solo
            a campos numéricos o de moneda. Los cambios se guardan al momento.
          </p>

          {cargando ? (
            <p style={{ color: "var(--text-3)" }}><i aria-hidden="true" className="ti ti-loader-2" style={{ marginRight: 6 }} />Cargando…</p>
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
                      <i aria-hidden="true" className={esTabla(h) ? "ti ti-table" : "ti ti-forms"} /> {h}
                      {esTabla(h) && <span className="hoja-tab-tipo">tabla</span>}
                      <span className="hoja-tab-count">{contarHoja(h)}</span>
                      {conProblema(h) && <i aria-hidden="true" className="ti ti-alert-triangle hoja-tab-alerta" title="Hay campos con problemas" />}
                    </button>
                  ))}
                </div>
              )}

              {infoHoja(hojaActiva) && (
                <div className="hoja-tipo">
                  <label htmlFor="tipo-hoja">Tipo de esta hoja</label>
                  <select id="tipo-hoja" disabled={cambiandoTipo}
                    value={infoHoja(hojaActiva)!.tipo_manual || "AUTO"}
                    onChange={(e) => cambiarTipoHoja(hojaActiva, e.target.value as "AUTO" | "TABLA" | "FORMULARIO")}>
                    <option value="AUTO">
                      Automático{!infoHoja(hojaActiva)!.tipo_manual
                        ? ` (detectado: ${esTabla(hojaActiva) ? "tabla" : "formulario"})` : ""}
                    </option>
                    <option value="TABLA">Tabla: se llena automáticamente</option>
                    <option value="FORMULARIO">Formulario: necesita campos</option>
                  </select>
                  <span className="hoja-tipo-ayuda">Cámbialo solo si EasyLit se equivocó al reconocerla.</span>
                </div>
              )}

              {esTabla(hojaActiva) && (
                <div className="hoja-aviso">
                  <i aria-hidden="true" className="ti ti-table" />
                  <div>
                    <strong>Esta hoja es una tabla: se llena automáticamente.</strong> Sus columnas
                    ({infoHoja(hojaActiva)!.columnas.join(", ")}) se completan con la tabla del
                    archivo de origen, así que no necesitan campos. Agrega campos aquí solo para
                    casillas que estén <em>arriba</em> de la tabla (ej. nombre del oferente).
                  </div>
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
                <div className={`campo-fila ${revision?.problemas[c.id] ? "con-problema" : ""}`} key={c.id}>
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

                  <button className="campo-del" title="Eliminar campo" onClick={() => setPorEliminar(c)}>
                    <i aria-hidden="true" className="ti ti-trash" />
                  </button>
                  {revision?.problemas[c.id] && (
                    <p className="campo-problema">
                      <i aria-hidden="true" className="ti ti-alert-triangle" /> Este campo no se podrá llenar: {revision.problemas[c.id]}
                    </p>
                  )}
                  {revision?.ubicaciones?.[c.id] && (
                    // Dónde se escribirá: así se ve que basta una etiqueta parecida.
                    <p className="campo-ubicacion">
                      <i aria-hidden="true" className="ti ti-circle-check" /> Se escribirá en la celda <strong>{revision.ubicaciones[c.id].celda}</strong>
                      {revision.ubicaciones[c.id].etiqueta && <>, junto a «{revision.ubicaciones[c.id].etiqueta}»</>}
                      {revision.ubicaciones[c.id].etiqueta && !revision.ubicaciones[c.id].exacta && <> (etiqueta parecida)</>}
                    </p>
                  )}
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
                <i aria-hidden="true" className="ti ti-plus" /> Añadir campo{hayHojas ? ` a "${hojaActiva}"` : ""}
              </button>
            </>
          )}
        </div>
        <div className="modal-foot">
          {/* Los cambios ya se guardaron al hacerlos: "Cerrar" sale sin revisar. */}
          <button className="btn" onClick={onCerrar}>Cerrar</button>
          <button className="btn btn-primary" onClick={terminar} disabled={revisando || cargando}>
            {revisando ? <><i aria-hidden="true" className="ti ti-loader-2" /> Revisando…</> : "Listo"}
          </button>
        </div>
      </div>
      {verAyuda && <AyudaCampos onCerrar={() => setVerAyuda(false)} />}
      {porEliminar && (
        <ConfirmarModal
          titulo="¿Eliminar este campo?"
          mensaje={`Se eliminará «${porEliminar.nombre}»${porEliminar.hoja_destino ? ` de la hoja «${porEliminar.hoja_destino}»` : ""}. `
            + "Esta acción no se puede deshacer: al transformar, esa casilla ya no se llenará, y las "
            + "transformaciones que lo usaban quedarán con ese dato sin asignar."}
          confirmar="Sí, eliminar"
          onCancelar={() => setPorEliminar(null)}
          onConfirmar={() => { quitar(porEliminar.id); setPorEliminar(null); }}
        />
      )}
      {resultado && (
        <ResultadoModal
          resultado={resultado}
          // ✓: listo, se cierra todo. ⚠/✗: "Aceptar" cierra igual; "Corregir" vuelve al editor.
          onAceptar={() => { setResultado(null); onCerrar(); }}
          secundario={resultado.estado === "exito" ? undefined
            : { texto: "Corregir campos", onClick: () => setResultado(null) }}
        />
      )}
    </div>
  );
}
