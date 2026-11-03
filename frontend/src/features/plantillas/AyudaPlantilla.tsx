/**
 * Guía paso a paso para subir una plantilla (botón «Ayuda» de Plantillas y del
 * formulario de nueva plantilla). Lo que dice debe seguir a PlantillaModal
 * (campos obligatorios), a lib/archivos.ts (formatos) y a CamposModal.
 */
import { GuiaPasos, type PasoGuia } from "./AyudaCampos";

const PASOS: PasoGuia[] = [
  {
    titulo: "¿Qué es una plantilla?",
    icono: "ti ti-template",
    contenido: (
      <>
        <p>
          Es el <strong>formato Excel que exige el mandante</strong> (municipalidad, ministerio, empresa) y que
          hay que entregar lleno. EasyLit lo guarda una vez y después lo llena solo con los datos de cada
          licitación, respetando su diseño: colores, fórmulas y estilos.
        </p>
        <p>Subir una plantilla tiene 4 pasos:</p>
        <ol>
          <li>Preparar el archivo.</li>
          <li>Crear la plantilla con sus datos.</li>
          <li>Revisar sus hojas y agregar los campos.</li>
          <li>Presionar «Listo» y usarla.</li>
        </ol>
        <p className="ayuda-nota">
          <i aria-hidden="true" className="ti ti-info-circle" /> Una plantilla se crea <strong>una sola vez</strong> y
          sirve para todas las licitaciones de ese mandante.
        </p>
      </>
    ),
  },
  {
    titulo: "1. Prepara el archivo",
    icono: "ti ti-file-spreadsheet",
    contenido: (
      <>
        <ul>
          <li>Usa el <strong>archivo original del mandante</strong>, sin llenar y sin cambiarle el diseño.</li>
          <li>Debe ser <strong>.xlsx</strong> (Excel) o <strong>.csv</strong>.</li>
          <li>Si está en <strong>.xls</strong> (Excel antiguo): ábrelo en Excel, ve a <strong>Archivo → Guardar
            como</strong> y elige <strong>«Libro de Excel (.xlsx)»</strong>.</li>
          <li>El archivo no puede pesar más de 20 MB. Si pesa más, quítale imágenes u hojas que no se usen.</li>
        </ul>
        <p className="ayuda-nota">
          <i aria-hidden="true" className="ti ti-alert-triangle" /> Un archivo dañado o con el nombre cambiado
          (por ejemplo, un PDF renombrado a .xlsx) se rechaza con un aviso.
        </p>
      </>
    ),
  },
  {
    titulo: "2. Crea la plantilla",
    icono: "ti ti-square-plus",
    contenido: (
      <>
        <p>En <strong>Plantillas</strong>, presiona <strong>«Nueva plantilla»</strong> y completa:</p>
        <table className="ayuda-tabla">
          <tbody>
            <tr><th>Nombre *</th><td>Cómo la vas a reconocer. Ej.: «Formulario Identificación 2026».</td></tr>
            <tr><th>Mandante *</th><td>Para quién es el formato. Se guarda en MAYÚSCULAS, así cada empresa aparece una sola vez.</td></tr>
            <tr><th>Sector</th><td>Opcional. Ej.: Educación, Minería.</td></tr>
            <tr><th>Archivo *</th><td><strong>Arrastra</strong> el archivo al recuadro o <strong>haz clic</strong> en él para elegirlo.</td></tr>
          </tbody>
        </table>
        <p>Luego presiona <strong>«Crear y agregar campos»</strong>.</p>
      </>
    ),
  },
  {
    titulo: "3. Revisa las hojas y agrega los campos",
    icono: "ti ti-list-details",
    contenido: (
      <>
        <p>Al crearla se abre el <strong>editor de campos</strong>, con una pestaña por cada hoja del Excel:</p>
        <ul>
          <li><strong>Hojas de tabla</strong> (Ítem, Descripción, Cantidad…): se llenan automáticamente. No necesitan campos.</li>
          <li><strong>Hojas de formulario</strong>: agrega un <strong>campo</strong> por cada casilla que se llena con
            un dato (RUT, razón social, fecha…).</li>
          <li>Si EasyLit se equivocó al reconocer una hoja, cámbiala en <strong>«Tipo de esta hoja»</strong>.</li>
        </ul>
        <p className="ayuda-nota">
          <i aria-hidden="true" className="ti ti-help" /> Dentro del editor, el botón <strong>?</strong> explica en
          detalle cómo llenar cada campo.
        </p>
      </>
    ),
  },
  {
    titulo: "4. Presiona «Listo» y úsala",
    icono: "ti ti-circle-check",
    contenido: (
      <>
        <ul>
          <li><strong>«Listo»</strong> revisa la plantilla y te dice si todo está bien (✓) o qué hay que corregir (⚠),
            con la hoja y el campo.</li>
          <li>Los cambios se guardan al momento: puedes cerrar y volver después con el botón de campos de la tarjeta.</li>
          <li>Para transformar una licitación con ella, presiona <strong>▶ (Usar)</strong> en su tarjeta: se abre
            «Transformar» con la plantilla ya elegida.</li>
        </ul>
        <p className="ayuda-nota">
          <i aria-hidden="true" className="ti ti-info-circle" /> El archivo de una plantilla no se puede cambiar
          después de creada. Si el mandante cambia su formato, crea una plantilla nueva.
        </p>
      </>
    ),
  },
];

export default function AyudaPlantilla({ onCerrar }: { onCerrar: () => void }) {
  return <GuiaPasos pasos={PASOS} onCerrar={onCerrar} />;
}
