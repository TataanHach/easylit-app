/**
 * Reglas de contraseña. Son las mismas que valida el backend
 * (apps/usuarios/validadores.py); aquí sirven para avisar mientras se escribe.
 */
export const CONTRASENA_MIN = 6;
export const CONTRASENA_MAX = 18;

export interface Requisito {
  texto: string;
  cumple: (pw: string) => boolean;
}

// Especial = cualquier cosa que no sea letra, número ni espacio (ñ y á cuentan como letras).
const esEspecial = (c: string) => !/[\p{L}\p{N}\s]/u.test(c);

export const REQUISITOS_CONTRASENA: Requisito[] = [
  {
    texto: `Entre ${CONTRASENA_MIN} y ${CONTRASENA_MAX} caracteres`,
    cumple: (pw) => pw.length >= CONTRASENA_MIN && pw.length <= CONTRASENA_MAX,
  },
  { texto: "Al menos una mayúscula (A-Z)", cumple: (pw) => /\p{Lu}/u.test(pw) },
  { texto: "Al menos un número (0-9)", cumple: (pw) => /\p{N}/u.test(pw) },
  { texto: "Al menos un carácter especial (! @ # $ % & * ? -)", cumple: (pw) => [...pw].some(esEspecial) },
];

export function contrasenaValida(pw: string): boolean {
  return REQUISITOS_CONTRASENA.every((r) => r.cumple(pw));
}
