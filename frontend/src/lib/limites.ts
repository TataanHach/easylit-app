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

/** Quita los espacios del inicio y del final (no se usa en contraseñas). */
export function limpiarTexto(texto: string): string {
  return texto.trim();
}
