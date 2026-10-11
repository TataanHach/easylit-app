/**
 * Largo máximo de cada campo de texto. Coinciden con el `max_length` de los
 * modelos del backend, para que el usuario no pueda escribir más de lo que la
 * base de datos acepta.
 */
import { configuracionActual } from "./configuracion";

export const LIMITES = {
  email: 254,
  tokenInvitacion: 64,
  rut: 12,                  // "12.345.678-9"
  nombrePlantilla: 200,
  mandante: 200,
  sector: 100,
  nombreCampo: 150,
  etiquetaBusqueda: 150,
  nombreTransformacion: 200,
} as const;

/**
 * Problema de peso del archivo, en palabras del usuario, o "" si está bien.
 * El máximo (ARCHIVO_MAX_MB) lo define el backend y llega por /api/config/.
 */
export function problemaTamano(f: File): string {
  const maxMb = configuracionActual().archivo_max_mb;
  const mb = f.size / (1024 * 1024);
  if (mb <= maxMb) return "";
  return `«${f.name}» pesa ${mb.toFixed(1).replace(".", ",")} MB y el máximo es ${maxMb} MB. `
    + "Quita hojas o filas que no sean necesarias (o guárdalo sin imágenes) y vuelve a subirlo.";
}

/** Quita los espacios del inicio y del final (no se usa en contraseñas). */
export function limpiarTexto(texto: string): string {
  return texto.trim();
}
