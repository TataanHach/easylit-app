/**
 * Guía paso a paso de los campos de una plantilla (botón "?" del editor).
 *
 * Las "fotos" son ilustraciones hechas aquí mismo (mini hojas de Excel en
 * HTML): así siempre coinciden con cómo funciona la app y se ven bien en
 * cualquier pantalla. Lo que dicen debe seguir a services/generacion.py
 * (ubicar_campo, _escribir_valor) y a services/normalizacion.py.
 */
import { useEffect, useState, type ReactNode } from "react";
import "./ayuda-campos.css";

/** Mini hoja de Excel: filas de celdas con letras de columna y números de fila. */
function MiniExcel({ filas, columnas = ["A", "B", "C"], pie }: {
  filas: { celdas: { texto?: string; clase?: string }[]; clase?: string }[];
  columnas?: string[];
  pie?: ReactNode;
}) {
  return (
    <figure className="mx">
      <table className="mx-tabla" aria-hidden="true">
        <thead><tr><th />{columnas.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {filas.map((f, i) => (
            <tr key={i} className={f.clase}>
              <th>{i + 1}</th>
              {f.celdas.map((c, j) => <td key={j} className={c.clase}>{c.texto}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {pie && <figcaption>{pie}</figcaption>}
    </figure>
  );
}

// 6 pasos cortos, en el orden en que se usa el editor: qué es un campo, las hojas,
// cuándo agregarlo, dónde se escribe, tipo/formato y la revisión final.
// Las mini pantallas del editor usan sus mismas clases (plantillas.css) para verse igual.
const PASOS: { titulo: string; icono: string; contenido: ReactNode }[] = [
  {
    titulo: "¿Qué es un campo?",
    icono: "ti ti-forms",
    contenido: (
      <>
        <p>
          Una <strong>casilla del Excel</strong> que EasyLit llena con un dato de la licitación: el RUT, la razón
          social, la fecha de apertura…
        </p>
        <MiniExcel
          filas={[
            { celdas: [{ texto: "RUT:", clase: "etiqueta" }, { texto: "76.453.212-0", clase: "dato" }, {}] },
            { celdas: [{ texto: "Razón social:", clase: "etiqueta" }, { texto: "Constructora SpA", clase: "dato" }, {}] },
          ]}
          pie={<><span className="mx-marca etiqueta" /> Ya está en tu Excel · <span className="mx-marca dato" /> Lo llena EasyLit</>}
        />
        <p className="ayuda-nota">
          <i aria-hidden="true" className="ti ti-table" /> Las hojas de <strong>tabla</strong> (Ítem, Descripción, Cantidad…) se llenan automáticamente
          con la tabla del origen: <strong>no necesitan campos</strong>.
        </p>
      </>
    ),
  },
  {
    titulo: "Cada hoja por separado",
    icono: "ti ti-files",
    contenido: (
      <>
        <p>
          Si el Excel tiene varias hojas, cada una tiene su <strong>pestaña</strong>. Los campos que agregas van a la
          hoja que tienes abierta.
        </p>
        <div className="hoja-tabs" aria-hidden="true">
          <span className="hoja-tab activa"><i className="ti ti-forms" /> Identificación <span className="hoja-tab-count">7</span></span>
          <span className="hoja-tab"><i className="ti ti-table" /> Materiales <span className="hoja-tab-tipo">tabla</span> <span className="hoja-tab-count">0</span></span>
          <span className="hoja-tab"><i className="ti ti-forms" /> Oferta <span className="hoja-tab-count">3</span> <i className="ti ti-alert-triangle hoja-tab-alerta" /></span>
        </div>
        <p>El número dice cuántos campos tiene la hoja, y <span className="ayuda-aviso">⚠</span> que alguno tiene un problema.</p>
        <p className="ayuda-nota">
          <i aria-hidden="true" className="ti ti-info-circle" /> <strong>Tipo de esta hoja:</strong> EasyLit reconoce solo si
          es tabla o formulario. Cámbialo solo si se equivocó.
        </p>
      </>
    ),
  },
  {
    titulo: "¿Cuándo agregar un campo?",
    icono: "ti ti-checklist",
    contenido: (
      <>
        <div className="ayuda-dos">
          <div className="ayuda-si">
            <p className="ayuda-sub"><i aria-hidden="true" className="ti ti-circle-check" /> Sí</p>
            <ul>
              <li>Cada casilla de un formulario que se llena con un dato de la licitación.</li>
              <li>Casillas <strong>sobre</strong> una tabla (oferente, fecha…).</li>
            </ul>
          </div>
          <div className="ayuda-no">
            <p className="ayuda-sub"><i aria-hidden="true" className="ti ti-circle-x" /> No</p>
            <ul>
              <li>Columnas de una tabla: se llenan automáticamente.</li>
              <li>Títulos, fórmulas (totales, IVA) o casillas de firma y timbre.</li>
            </ul>
          </div>
        </div>
        <p className="ayuda-nota">
          <i aria-hidden="true" className="ti ti-info-circle" /> Si un campo cae <strong>dentro</strong> de una tabla, el editor
          te avisa que sobra y lo puedes eliminar.
        </p>
      </>
    ),
  },
  {
    titulo: "Nombre y etiqueta",
    icono: "ti ti-search",
    contenido: (
      <>
        <ul>
          <li>
            <strong>Nombre:</strong> claro, porque la IA lo usa para encontrar el dato.{" "}
            <span className="ayuda-ok">✓ «RUT Empresa»</span> <span className="ayuda-mal">✗ «Campo1»</span>
          </li>
          <li>
            <strong>Etiqueta de búsqueda:</strong> el texto que ya está en tu Excel. El dato se escribe en la
            celda de su <strong>derecha</strong>. Si la dejas vacía, se busca el nombre.
          </li>
        </ul>
        <MiniExcel
          filas={[
            { celdas: [{ texto: "RUT del oferente:", clase: "etiqueta" }, { texto: "← aquí", clase: "dato" }, {}] },
            { celdas: [{ texto: "Dirección:" }, {}, {}] },
          ]}
        />
        <p className="ayuda-sub">Bajo cada campo, el editor te dice qué encontró:</p>
        <p className="campo-ubicacion">
          <i aria-hidden="true" className="ti ti-circle-check" /> Se escribirá en la celda <strong>B1</strong>, junto a
          «RUT del oferente:» (etiqueta parecida)
        </p>
        <p className="campo-problema">
          <i aria-hidden="true" className="ti ti-alert-triangle" /> Este campo no se podrá llenar: no se encontró el
          texto «Giro» en la hoja «Identificación»…
        </p>
        <p className="ayuda-nota">
          <i aria-hidden="true" className="ti ti-info-circle" /> La etiqueta no tiene que ser exacta: basta un texto parecido.
        </p>
      </>
    ),
  },
  {
    titulo: "Tipo y formato",
    icono: "ti ti-category",
    contenido: (
      <>
        <table className="ayuda-tabla">
          <tbody>
            <tr><th>Texto</th><td>Nombres, direcciones. Es el tipo por defecto.</td></tr>
            <tr><th>Número</th><td>Montos y cantidades. Es el único que usa <strong>Formato</strong>: entero, decimal, pesos $, pesos con decimales, % o UF.</td></tr>
            <tr><th>Fecha</th><td>Queda como fecha de Excel (15-08-2024).</td></tr>
            <tr><th>Unidad</th><td>m2, m3, kg… «1200 mts2» queda «1200 m2».</td></tr>
          </tbody>
        </table>
        <p className="ayuda-nota">
          <i aria-hidden="true" className="ti ti-info-circle" /> En los demás tipos, la columna Formato queda desactivada.
        </p>
      </>
    ),
  },
  {
    titulo: "Revisar y terminar",
    icono: "ti ti-circle-check",
    contenido: (
      <>
        <p>
          Cada cambio <strong>se guarda al instante</strong>. Cuando termines, presiona <strong>«Listo»</strong> y
          EasyLit revisa la plantilla completa:
        </p>
        <table className="ayuda-tabla">
          <tbody>
            <tr><th><span className="ayuda-ok">✓</span> Correcta</th><td>Todos los campos encontraron su casilla.</td></tr>
            <tr><th><span className="ayuda-aviso">⚠</span> Por revisar</th><td>Lista, hoja por hoja, lo que no se llenará. Con <strong>«Corregir campos»</strong> vuelves al editor.</td></tr>
            <tr><th><span className="ayuda-mal">✗</span> Error</th><td>No se pudo leer el Excel, o la plantilla no tiene nada que llenar.</td></tr>
          </tbody>
        </table>
      </>
    ),
  },
];

export default function AyudaCampos({ onCerrar }: { onCerrar: () => void }) {
  const [paso, setPaso] = useState(0);
  const actual = PASOS[paso];
  const ultimo = paso === PASOS.length - 1;

  // Flechas para avanzar y retroceder; Escape cierra.
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCerrar();
      if (e.key === "ArrowRight") setPaso((p) => Math.min(PASOS.length - 1, p + 1));
      if (e.key === "ArrowLeft") setPaso((p) => Math.max(0, p - 1));
    };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [onCerrar]);

  return (
    <div className="ayuda-overlay">
      <div className="ayuda-modal" role="dialog" aria-modal="true" aria-labelledby="ayuda-titulo">
        <div className="ayuda-head">
          <span className="ayuda-contador" aria-live="polite">Paso {paso + 1} de {PASOS.length}</span>
          <button className="modal-close" onClick={onCerrar} aria-label="Cerrar ayuda"><i aria-hidden="true" className="ti ti-x" /></button>
        </div>
        {/* key: al cambiar de paso, la animación de entrada se repite. */}
        <div className="ayuda-cuerpo" key={paso}>
          <h2 id="ayuda-titulo"><i aria-hidden="true" className={actual.icono} /> {actual.titulo}</h2>
          {actual.contenido}
        </div>
        <div className="ayuda-foot">
          <div className="ayuda-puntos" role="group" aria-label="Pasos">
            {PASOS.map((p, i) => (
              <button key={p.titulo} className={i === paso ? "activo" : ""} onClick={() => setPaso(i)}
                aria-label={`Paso ${i + 1}: ${p.titulo}`} aria-current={i === paso ? "step" : undefined} />
            ))}
          </div>
          <div className="ayuda-botones">
            <button className="btn" onClick={() => setPaso(paso - 1)} disabled={paso === 0}>
              <i aria-hidden="true" className="ti ti-arrow-left" /> Anterior
            </button>
            {ultimo
              ? <button className="btn btn-primary" onClick={onCerrar}>Entendido</button>
              : <button className="btn btn-primary" onClick={() => setPaso(paso + 1)}>
                  Siguiente <i aria-hidden="true" className="ti ti-arrow-right" />
                </button>}
          </div>
        </div>
      </div>
    </div>
  );
}
