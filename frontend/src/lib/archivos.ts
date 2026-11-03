/**
 * Revisión de los archivos que se suben (plantillas y Excel de origen) y
 * arrastrar y soltar. La misma regla la vuelve a aplicar el backend
 * (apps/common/archivos.py): aquí sirve para avisar antes de subir.
 */
import { useState, type DragEvent } from "react";
import { problemaTamano } from "./limites";

export const ACEPTA_ARCHIVO = ".xlsx,.csv";

/** Problema del archivo en palabras del usuario, o "" si está bien. */
export async function problemaArchivo(f: File): Promise<string> {
  const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
  if (ext !== "xlsx" && ext !== "csv") {
    const antiguo = ["xls", "xlsm", "xlsb"].includes(ext)
      ? " Ábrelo en Excel y usa «Guardar como» → «Libro de Excel (.xlsx)»."
      : "";
    return `«${f.name}» no es un archivo .xlsx ni .csv. Sube el archivo en uno de esos formatos.${antiguo}`;
  }
  if (f.size === 0) {
    return `«${f.name}» está vacío. Revisa que se haya guardado bien y vuelve a subirlo.`;
  }
  const peso = problemaTamano(f);
  if (peso) return peso;

  // Un .xlsx de verdad empieza como ZIP («PK»); un CSV es texto (sin bytes nulos).
  const inicio = new Uint8Array(await f.slice(0, 4096).arrayBuffer());
  if (ext === "xlsx" && !(inicio[0] === 0x50 && inicio[1] === 0x4b)) {
    return `«${f.name}» no es un Excel válido: puede estar dañado o ser otro tipo de archivo con el nombre cambiado. Ábrelo en Excel, guárdalo como .xlsx y vuelve a subirlo.`;
  }
  if (ext === "csv" && inicio.includes(0)) {
    return `«${f.name}» no es un CSV válido: no es texto. Si es un Excel, súbelo como .xlsx.`;
  }
  return "";
}

/**
 * Arrastrar y soltar un archivo sobre una zona. `encima` sirve para resaltarla
 * mientras el archivo está sobre ella; `props` van en el elemento de la zona.
 */
export function useArrastrar(alSoltar: (f: File) => void) {
  const [encima, setEncima] = useState(false);
  const props = {
    onDragEnter: (e: DragEvent) => { e.preventDefault(); setEncima(true); },
    onDragOver: (e: DragEvent) => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; },
    onDragLeave: (e: DragEvent) => {
      // Al pasar sobre un hijo también llega dragleave: solo vale si sale de la zona.
      if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setEncima(false);
    },
    onDrop: (e: DragEvent) => {
      e.preventDefault();
      setEncima(false);
      const f = e.dataTransfer.files?.[0];
      if (f) alSoltar(f);
    },
  };
  return { encima, props };
}
