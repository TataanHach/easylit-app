/**
 * Largo máximo de cada campo de texto. Coinciden con el `max_length` de los
 * modelos del backend, para que el usuario no pueda escribir más de lo que la
 * base de datos acepta.
 */
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
 * Peso máximo de los archivos que se suben (plantillas y Excel de origen). Es el
 * mismo que valida el backend (apps/common/archivos.py).
 */
export const ARCHIVO_MAX_MB = 20;

/** Problema de peso del archivo, en palabras del usuario, o "" si está bien. */
export function problemaTamano(f: File): string {
  const mb = f.size / (1024 * 1024);
  if (mb <= ARCHIVO_MAX_MB) return "";
  return `«${f.name}» pesa ${mb.toFixed(1).replace(".", ",")} MB y el máximo es ${ARCHIVO_MAX_MB} MB. `
    + "Quita hojas o filas que no sean necesarias (o guárdalo sin imágenes) y vuelve a subirlo.";
}

/** Quita los espacios del inicio y del final (no se usa en contraseñas). */
export function limpiarTexto(texto: string): string {
  return texto.trim();
}
