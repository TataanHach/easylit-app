/**
 * Utilidades de RUT chileno.
 *
 * Solo para feedback inmediato en el formulario. La validación de verdad está en
 * el backend; nunca se confía en el navegador para reglas de negocio.
 */

/** Formatea con puntos y guion: 123456789 → 12.345.678-9 */
export function formatearRut(valor: string): string {
  const limpio = valor.replace(/[^0-9kK]/g, "").toUpperCase();
  if (limpio.length <= 1) return limpio;
  const cuerpo = limpio.slice(0, -1);
  const dv = limpio.slice(-1);
  const conPuntos = cuerpo.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${conPuntos}-${dv}`;
}

/** Valida el dígito verificador con el módulo 11. */
export function rutValido(valor: string): boolean {
  const limpio = valor.replace(/[.\-]/g, "").toUpperCase();
  if (limpio.length < 2) return false;
  const cuerpo = limpio.slice(0, -1);
  const dv = limpio.slice(-1);
  if (!/^\d+$/.test(cuerpo)) return false;

  let suma = 0;
  let mult = 2;
  for (let i = cuerpo.length - 1; i >= 0; i--) {
    suma += parseInt(cuerpo[i], 10) * mult;
    mult = mult === 7 ? 2 : mult + 1;
  }
  const resto = 11 - (suma % 11);
  const esperado = resto === 11 ? "0" : resto === 10 ? "K" : String(resto);
  return dv === esperado;
}
