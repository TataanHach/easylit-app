/**
 * Login con Firebase (opcional).
 *
 * Si las variables VITE_FIREBASE_* están definidas, Firebase hace el inicio de
 * sesión y cada petición al backend lleva su token. Si no, la app usa el login
 * propio con JWT (desarrollo local), sin cambiar nada más.
 */
import { initializeApp } from "firebase/app";
import {
  browserSessionPersistence,
  getAuth,
  onAuthStateChanged,
  setPersistence,
  type Auth,
  type User,
} from "firebase/auth";

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const firebaseActivo = Boolean(config.apiKey && config.projectId);

export const auth: Auth | null = firebaseActivo ? getAuth(initializeApp(config)) : null;

// La sesión dura lo que la pestaña, igual que el login propio (sessionStorage):
// al cerrar el navegador hay que volver a entrar.
const persistencia = auth ? setPersistence(auth, browserSessionPersistence) : Promise.resolve();

/** Espera a que Firebase diga si hay una sesión abierta (al recargar la página). */
export async function esperarSesion(): Promise<User | null> {
  if (!auth) return null;
  await persistencia;
  return new Promise((resolve) => {
    const dejar = onAuthStateChanged(auth, (usuario) => {
      dejar();
      resolve(usuario);
    });
  });
}

/** Mensaje en palabras del usuario para un error de Firebase, o "" si no lo es. */
export function mensajeFirebase(e: unknown): string {
  const codigo = (e as { code?: string })?.code ?? "";
  if (!codigo.startsWith("auth/")) return "";
  switch (codigo) {
    case "auth/invalid-credential":
    case "auth/wrong-password":
    case "auth/user-not-found":
      return "La contraseña no es correcta. Revisa las mayúsculas y vuelve a intentarlo.";
    case "auth/too-many-requests":
      return "Demasiados intentos fallidos. Espera unos minutos y vuelve a intentarlo.";
    case "auth/network-request-failed":
      return "No hay conexión con el servicio de inicio de sesión. Revisa tu internet y vuelve a intentarlo.";
    case "auth/user-disabled":
      return "Tu cuenta está deshabilitada. Pídele a tu gerente que la revise.";
    default:
      return "No se pudo iniciar sesión. Intenta de nuevo; si se repite, avisa al administrador.";
  }
}
