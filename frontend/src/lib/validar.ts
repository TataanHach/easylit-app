/**
 * Validaciones de formulario con mensajes propios.
 *
 * Los formularios usan `noValidate`: en vez del globo del navegador ("Completa
 * este campo"), cada campo muestra debajo qué está mal y qué hacer. El backend
 * repite estas reglas, así que saltárselas editando el HTML no sirve de nada.
 *
 * Cada función devuelve el problema en palabras del usuario, o "" si está bien.
 */
import { LIMITES } from "./limites";

// Algo@algo.dominio, sin espacios. Igual de permisivo que el EmailField del backend.
const FORMATO_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// --- Caracteres permitidos (misma regla que apps/common/textos.py) ---
// Además de letras (con tildes y ñ), números y espacios:
const SIGNOS_TEXTO = ".,-()/&'’°º";   // nombre de plantilla, mandante, sector
const SIGNOS_PERSONA = ".'’-";        // nombres de personas (sin números)
const AYUDA_TEXTO = "Usa solo letras, números, espacios y . , - ( ) / & ' °";
const AYUDA_PERSONA = "Usa solo letras, espacios y . ' -";
const esLetra = (c: string) => /\p{L}/u.test(c);
const esNumero = (c: string) => /\p{N}/u.test(c);
const esEspacio = (c: string) => /\s/u.test(c);

// Correo de un usuario nuevo: letras, números y . _ - + antes de la @, y un dominio con punto.
const CORREO_ESTRICTO = /^[A-Za-z0-9._+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/;

/**
 * "" si el texto solo tiene caracteres aceptados; si no, cuáles sobran y qué se
 * puede usar. `persona` = nombre de una persona (sin números ni & / ( )).
 */
export function problemaCaracteres(texto: string, persona = false): string {
  const permitido = persona
    ? (c: string) => esLetra(c) || esEspacio(c) || SIGNOS_PERSONA.includes(c)
    : (c: string) => esLetra(c) || esNumero(c) || esEspacio(c) || SIGNOS_TEXTO.includes(c);
  const malos = [...new Set([...texto].filter((c) => !permitido(c)))];
  if (!malos.length) return "";
  return `tiene caracteres que no se aceptan: ${malos.join(" ")}. ${persona ? AYUDA_PERSONA : AYUDA_TEXTO}.`;
}

/** Correo para invitar a alguien: más estricto que el del login (sin # $ " …). */
export function problemaCorreoNuevo(correo: string): string {
  if (!correo) return "Falta el correo. Escríbelo como nombre@empresa.cl.";
  if (correo.length > LIMITES.email) return `El correo puede tener como máximo ${LIMITES.email} caracteres.`;
  if (!CORREO_ESTRICTO.test(correo)) {
    return "El correo no es válido o tiene caracteres que no se aceptan. Usa solo letras, números y . _ - + antes de la @, como nombre@empresa.cl.";
  }
  return "";
}

export function problemaCorreo(correo: string): string {
  if (!correo) return "Escribe tu correo electrónico para continuar.";
  if (correo.length > LIMITES.email) return `El correo puede tener como máximo ${LIMITES.email} caracteres.`;
  if (!FORMATO_CORREO.test(correo)) {
    return "El correo no tiene un formato válido. Debe ser como nombre@empresa.cl (con @ y sin espacios).";
  }
  return "";
}
