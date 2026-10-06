/**
 * Traduce un error de una llamada al backend a un mensaje para el usuario:
 * un título (qué falló) y un detalle (por qué y qué hacer).
 *
 * `accion` completa la frase "No se pudo …", ej. "eliminar la transformación".
 */
import axios from "axios";

export interface MensajeError {
  titulo: string;
  detalle: string;
}

// Nombres legibles de los campos que el backend puede devolver en una validación.
const CAMPOS: Record<string, string> = {
  archivo_origen: "Archivo",
  nombre_origen: "Nombre del archivo",
  nombre: "Nombre",
  plantilla: "Plantilla",
  mandante: "Empresa",
  archivo: "Archivo",
  campo: "Campo",
  destino_campo: "Campo destino",
};

/** Junta los mensajes de un cuerpo de error de DRF en un solo texto. */
function textoDelBackend(data: unknown): string {
  if (!data) return "";
  if (typeof data === "string") {
    // Una página HTML (ej. error 500 de Django) no sirve como mensaje.
    return data.trim().startsWith("<") ? "" : data;
  }
  if (Array.isArray(data)) return data.map(textoDelBackend).filter(Boolean).join(" ");
  if (typeof data === "object") {
    const obj = data as Record<string, unknown>;
    if (typeof obj.detail === "string") return obj.detail;
    return Object.entries(obj)
      .map(([campo, valor]) => {
        const texto = textoDelBackend(valor);
        if (!texto) return "";
        return campo === "non_field_errors" || campo === "error"
          ? texto
          : `${CAMPOS[campo] ?? campo}: ${texto}`;
      })
      .filter(Boolean)
      .join(" ");
  }
  return "";
}

export function describirError(e: unknown, accion: string): MensajeError {
  const titulo = `No se pudo ${accion}`;

  if (!axios.isAxiosError(e)) {
    // Error del código de la página, no del servidor: se deja en la consola y se
    // muestra el motivo técnico para poder reportarlo.
    console.error(e);
    const motivo = e instanceof Error ? ` (${e.message})` : "";
    return {
      titulo,
      detalle: `Ocurrió un error inesperado en la página${motivo}. Recárgala (Ctrl+F5) e intenta de nuevo; si se repite, avisa al administrador con este mensaje.`,
    };
  }
  if (!e.response) {
    return {
      titulo,
      detalle: "No hay conexión con el servidor. Revisa tu internet (o que el backend esté encendido) y vuelve a intentarlo.",
    };
  }

  const delBackend = textoDelBackend(e.response.data);
  switch (e.response.status) {
    case 400:
      return { titulo, detalle: delBackend || "Los datos enviados no son válidos. Revísalos e intenta de nuevo." };
    case 401:
      return { titulo, detalle: "Tu sesión expiró. Vuelve a iniciar sesión e intenta de nuevo." };
    case 403:
      return { titulo, detalle: delBackend || "No tienes permiso para hacer esto. Si lo necesitas, pídeselo a tu gerente." };
    case 404:
      return { titulo, detalle: delBackend || "No se encontró lo que buscas. Puede que alguien lo haya eliminado; recarga la página." };
    case 413:
      return { titulo, detalle: "El archivo es demasiado grande. Quita hojas o filas que no sean necesarias y vuelve a subirlo." };
    default:
      if (e.response.status >= 500) {
        return {
          titulo,
          detalle: "El servidor tuvo un problema interno. Intenta de nuevo en unos minutos; si se repite, avisa al administrador.",
        };
      }
      return { titulo, detalle: delBackend || "Ocurrió un error inesperado. Intenta de nuevo." };
  }
}
