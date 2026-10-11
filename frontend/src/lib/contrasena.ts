/**
 * Reglas de contraseña. El largo mínimo y máximo vienen del backend
 * (/api/config/, que lee CONTRASENA_MIN/MAX); el resto es la misma regla de
 * apps/usuarios/validadores.py. Aquí sirven para avisar mientras se escribe.
 */
import type { Configuracion } from "./configuracion";

export interface Requisito {
  texto: string;
  cumple: (pw: string) => boolean;
}

// Especial = cualquier cosa que no sea letra, número ni espacio (ñ y á cuentan como letras).
const esEspecial = (c: string) => !/[\p{L}\p{N}\s]/u.test(c);

export function requisitosContrasena(cfg: Configuracion): Requisito[] {
  const { contrasena_min: min, contrasena_max: max } = cfg;
  return [
    { texto: `Entre ${min} y ${max} caracteres`, cumple: (pw) => pw.length >= min && pw.length <= max },
    { texto: "Al menos una mayúscula (A-Z)", cumple: (pw) => /\p{Lu}/u.test(pw) },
    { texto: "Al menos un número (0-9)", cumple: (pw) => /\p{N}/u.test(pw) },
    { texto: "Al menos un carácter especial (! @ # $ % & * ? -)", cumple: (pw) => [...pw].some(esEspecial) },
  ];
}
