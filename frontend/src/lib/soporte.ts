/**
 * Canales de soporte de EasyLit (los usan la burbuja y el footer).
 *
 * Se configuran con variables de entorno, no van escritos en el código porque
 * son datos de contacto del equipo:
 *   VITE_SOPORTE_CORREO    soporte@empresa.cl
 *   VITE_SOPORTE_WHATSAPP  56912345678  (con código de país, solo números)
 */
export const SOPORTE_CORREO = (import.meta.env.VITE_SOPORTE_CORREO ?? "").trim();
export const SOPORTE_WHATSAPP = (import.meta.env.VITE_SOPORTE_WHATSAPP ?? "").replace(/\D/g, "");

export function enlaceCorreoSoporte(texto = ""): string {
  const cuerpo = texto ? `&body=${encodeURIComponent(texto)}` : "";
  return `mailto:${SOPORTE_CORREO}?subject=${encodeURIComponent("Soporte EasyLit")}${cuerpo}`;
}

export function enlaceWhatsappSoporte(texto = ""): string {
  return `https://wa.me/${SOPORTE_WHATSAPP}${texto ? `?text=${encodeURIComponent(texto)}` : ""}`;
}
