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

const PASOS: { titulo: string; icono: string; contenido: ReactNode }[] = [
  {
    titulo: "¿Qué es un campo?",
    icono: "ti ti-forms",
    contenido: (
      <>
        <p>
          Un <strong>campo</strong> es una casilla del Excel de la plantilla que EasyLit llena con un dato
          del archivo de la licitación. Por ejemplo: el RUT, la razón social o la fecha de apertura.
        </p>
        <p>
          Cada campo le dice al sistema <strong>dónde</strong> escribir (buscando su etiqueta en la hoja) y
          <strong> qué</strong> escribir (la IA elige el dato del origen que corresponde, y tú puedes
          cambiarlo en el mapeo).
        </p>
        <MiniExcel
          filas={[
            { celdas: [{ texto: "RUT:", clase: "etiqueta" }, { texto: "76.453.212-0", clase: "dato" }, {}] },
            { celdas: [{ texto: "Razón social:", clase: "etiqueta" }, { texto: "Constructora SpA", clase: "dato" }, {}] },
          ]}
          pie={<><span className="mx-marca etiqueta" /> Etiqueta (ya está en tu Excel) · <span className="mx-marca dato" /> Lo que llena EasyLit</>}
        />
      </>
    ),
  },
  {
    titulo: "Formulario o tabla: ¿qué hojas necesitan campos?",
    icono: "ti ti-table",
    contenido: (
      <>
        <p>Arriba ves una pestaña por cada hoja del Excel. EasyLit las reconoce solo:</p>
        <ul>
          <li>
            <strong><i className="ti ti-forms" /> Formulario</strong>: casillas sueltas con su etiqueta
            («RUT:», «Dirección:»). <strong>Necesitan un campo por casilla.</strong>
          </li>
          <li>
            <strong><i className="ti ti-table" /> Tabla</strong> (con la etiqueta «tabla»): una fila de
            encabezados como Ítem, Descripción, Cantidad, Precio. <strong>Se llena sola</strong> con la tabla del
            archivo de origen, fila por fila. <strong>No le agregues campos</strong> a sus columnas.
          </li>
        </ul>
        <MiniExcel
          columnas={["A", "B", "C", "D"]}
          filas={[
            { celdas: [{ texto: "Ítem", clase: "encabezado" }, { texto: "Descripción", clase: "encabezado" }, { texto: "Cantidad", clase: "encabezado" }, { texto: "Precio", clase: "encabezado" }] },
            { celdas: [{ texto: "1", clase: "auto" }, { texto: "Cemento", clase: "auto" }, { texto: "40", clase: "auto" }, { texto: "$ 6.990", clase: "auto" }] },
            { celdas: [{ texto: "2", clase: "auto" }, { texto: "Fierro 12 mm", clase: "auto" }, { texto: "120", clase: "auto" }, { texto: "$ 8.450", clase: "auto" }] },
          ]}
          pie={<><span className="mx-marca auto" /> Las filas de la tabla se copian solas desde el origen: sin campos</>}
        />
        <p className="ayuda-nota">
          <i className="ti ti-info-circle" /> Si una hoja con tabla tiene casillas <strong>encima</strong> de la tabla
          (por ejemplo «Nombre del oferente»), esas sí llevan campo.
        </p>
      </>
    ),
  },
  {
    titulo: "Qué agregar y qué no",
    icono: "ti ti-checklist",
    contenido: (
      <div className="ayuda-dos">
        <div className="ayuda-si">
          <p className="ayuda-sub"><i className="ti ti-circle-check" /> Sí agrega un campo para</p>
          <ul>
            <li>Cada casilla de un formulario que deba llenarse con un dato de la licitación.</li>
            <li>Casillas que están encima de una tabla (datos del oferente, fecha, etc.).</li>
          </ul>
        </div>
        <div className="ayuda-no">
          <p className="ayuda-sub"><i className="ti ti-circle-x" /> No agregues campos para</p>
          <ul>
            <li>Columnas de una hoja de <strong>tabla</strong>: se llenan solas.</li>
            <li>Títulos o textos fijos del formato («FORMULARIO 1: IDENTIFICACIÓN»).</li>
            <li>Celdas con <strong>fórmulas</strong> (totales, IVA calculado): Excel las calcula.</li>
            <li>Casillas que el oferente completa a mano (firma, timbre).</li>
          </ul>
        </div>
      </div>
    ),
  },
  {
    titulo: "Nombre del campo",
    icono: "ti ti-tag",
    contenido: (
      <>
        <p>
          Es cómo identificas el campo, y <strong>la IA lo usa para encontrar el dato</strong> en el archivo de
          la licitación. Por eso conviene que sea claro:
        </p>
        <ul>
          <li><span className="ayuda-ok">✓ «RUT Empresa»</span>, <span className="ayuda-ok">✓ «Fecha de apertura»</span></li>
          <li><span className="ayuda-mal">✗ «Campo1»</span>, <span className="ayuda-mal">✗ «Dato»</span></li>
        </ul>
        <p>No puede haber dos campos con el mismo nombre en una plantilla.</p>
        <p className="ayuda-nota">
          <i className="ti ti-sparkles" /> Algunas palabras activan una limpieza automática del dato: si el nombre
          dice <strong>RUT</strong> (puntos y guion, si el dígito verificador es válido), <strong>correo</strong> (sin espacios),
          <strong> teléfono</strong> (solo el primer número) o <strong>representante</strong> (sin el RUT pegado
          al nombre).
        </p>
      </>
    ),
  },
  {
    titulo: "Etiqueta de búsqueda: dónde se escribe",
    icono: "ti ti-search",
    contenido: (
      <>
        <p>
          Es el <strong>texto que ya está en tu Excel</strong>, al lado de la casilla. EasyLit busca ese texto en la
          hoja y escribe el dato en la <strong>celda de su derecha</strong>.
        </p>
        <MiniExcel
          filas={[
            { celdas: [{ texto: "RUT del oferente:", clase: "etiqueta" }, { texto: "← aquí", clase: "dato" }, {}] },
            { celdas: [{ texto: "Dirección:" }, {}, {}] },
          ]}
          pie={<>Etiqueta de búsqueda <strong>«RUT del oferente»</strong> → el dato se escribe en <strong>B1</strong></>}
        />
        <ul>
          <li><strong>No tiene que ser exacta:</strong> basta con que coincida al menos la mitad de las palabras, sin
            importar mayúsculas, tildes ni los dos puntos. «rut oferente» encuentra «RUT del oferente:».</li>
          <li><strong>Si la dejas vacía</strong>, se busca el nombre del campo.</li>
          <li>Bajo cada campo verás <span className="ayuda-ok">✓ Se escribirá en la celda B1…</span> si la encontró, o un
            aviso <span className="ayuda-aviso">⚠</span> con el motivo si no.</li>
        </ul>
      </>
    ),
  },
  {
    titulo: "Tipo del dato",
    icono: "ti ti-category",
    contenido: (
      <>
        <p>Le dice a la IA qué clase de dato buscar y cómo escribirlo:</p>
        <table className="ayuda-tabla">
          <tbody>
            <tr><th>Texto</th><td>Nombres, direcciones, descripciones. Es el tipo por defecto.</td></tr>
            <tr><th>Número</th><td>Cantidades, montos, plazos. <strong>Habilita el formato</strong> (siguiente paso).</td></tr>
            <tr><th>Fecha</th><td>Se escribe como <strong>fecha real de Excel</strong> (15-08-2024), aunque en el origen
              diga «15 de agosto de 2024».</td></tr>
            <tr><th>Unidad</th><td>Unidades de medida (m2, m3, kg). «1200 mts2» queda «1200 m2».</td></tr>
          </tbody>
        </table>
      </>
    ),
  },
  {
    titulo: "Formato (solo para Número)",
    icono: "ti ti-currency-dollar",
    contenido: (
      <>
        <p>Cómo se ve el número en la celda. El valor queda como número real de Excel, así que las fórmulas funcionan.</p>
        <table className="ayuda-tabla">
          <tbody>
            <tr><th>Sin formato</th><td>Tal como viene.</td></tr>
            <tr><th>Número entero</th><td>1.234</td></tr>
            <tr><th>Decimal</th><td>1.234,56</td></tr>
            <tr><th>Pesos $</th><td>$ 1.234</td></tr>
            <tr><th>Pesos con decimales</th><td>$ 1.234,56</td></tr>
            <tr><th>Porcentaje %</th><td>12,5% (el dato debe venir como 12,5, no como 0,125)</td></tr>
            <tr><th>UF</th><td>1.234,56 UF</td></tr>
          </tbody>
        </table>
        <p className="ayuda-nota">
          <i className="ti ti-lock" /> Los campos en <strong>Pesos</strong> o <strong>UF</strong> son montos: «Limpiar con IA»
          nunca los envía, por privacidad (los limpia una regla fija). En la vista previa tienen además el ajuste de
          IVA (+ IVA o neto).
        </p>
      </>
    ),
  },
  {
    titulo: "Revisa y termina",
    icono: "ti ti-circle-check",
    contenido: (
      <>
        <ol>
          <li>Elige la <strong>pestaña</strong> de la hoja: el campo nuevo se agrega a la hoja que está abierta.</li>
          <li>Presiona <strong>«Añadir campo»</strong> y completa nombre, tipo, formato y etiqueta. Cada cambio se guarda
            al momento.</li>
          <li>Mira el mensaje bajo cada campo: <span className="ayuda-ok">✓</span> encontró su casilla,
            <span className="ayuda-aviso"> ⚠</span> hay algo que corregir.</li>
          <li>Presiona <strong>«Listo»</strong>: se revisa toda la plantilla y verás
            <span className="ayuda-ok"> ✓ todo correcto</span>, <span className="ayuda-aviso">⚠ qué revisar</span> o
            <span className="ayuda-mal"> ✗ qué falló</span>.</li>
        </ol>
        <p>«Cerrar» sale sin revisar: los cambios ya quedaron guardados.</p>
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
          <span className="ayuda-contador">Paso {paso + 1} de {PASOS.length}</span>
          <button className="modal-close" onClick={onCerrar} aria-label="Cerrar ayuda"><i className="ti ti-x" /></button>
        </div>
        {/* key: al cambiar de paso, la animación de entrada se repite. */}
        <div className="ayuda-cuerpo" key={paso}>
          <h2 id="ayuda-titulo"><i className={actual.icono} /> {actual.titulo}</h2>
          {actual.contenido}
        </div>
        <div className="ayuda-foot">
          <div className="ayuda-puntos" role="tablist" aria-label="Pasos">
            {PASOS.map((p, i) => (
              <button key={p.titulo} className={i === paso ? "activo" : ""} onClick={() => setPaso(i)}
                aria-label={`Paso ${i + 1}: ${p.titulo}`} aria-current={i === paso} />
            ))}
          </div>
          <div className="ayuda-botones">
            <button className="btn" onClick={() => setPaso(paso - 1)} disabled={paso === 0}>
              <i className="ti ti-arrow-left" /> Anterior
            </button>
            {ultimo
              ? <button className="btn btn-primary" onClick={onCerrar}>Entendido</button>
              : <button className="btn btn-primary" onClick={() => setPaso(paso + 1)}>
                  Siguiente <i className="ti ti-arrow-right" />
                </button>}
          </div>
        </div>
      </div>
    </div>
  );
}
