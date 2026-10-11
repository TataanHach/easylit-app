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

export function problemaCorreo(correo: string): string {
  if (!correo) return "Escribe tu correo electrónico para continuar.";
  if (correo.length > LIMITES.email) return `El correo puede tener como máximo ${LIMITES.email} caracteres.`;
  if (!FORMATO_CORREO.test(correo)) {
    return "El correo no tiene un formato válido. Debe ser como nombre@empresa.cl (con @ y sin espacios).";
  }
  return "";
}
