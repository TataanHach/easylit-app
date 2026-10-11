/**
 * Reglas de negocio que define el backend (settings/.env) y expone en
 * /api/config/: IVA, largo de contraseña y peso máximo de archivos.
 *
 * Se piden una vez al abrir la app. Los componentes usan `useConfiguracion()`;
 * el código que no es componente (validaciones, mensajes) usa
 * `configuracionActual()`.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export interface Configuracion {
  iva_porcentaje: number;
  contrasena_min: number;
  contrasena_max: number;
  archivo_max_mb: number;
}

// Solo de respaldo, mientras llega /api/config/ o si el servidor no responde.
// La fuente de verdad es el backend: cambiar ahí, no aquí.
const RESPALDO: Configuracion = {
  iva_porcentaje: 19,
  contrasena_min: 6,
  contrasena_max: 18,
  archivo_max_mb: 20,
};

let actual: Configuracion = RESPALDO;

export function configuracionActual(): Configuracion {
  return actual;
}

export async function cargarConfiguracion(): Promise<Configuracion> {
  const { data } = await api.get<Partial<Configuracion>>("/config/");
  actual = { ...RESPALDO, ...data };
  return actual;
}

export function useConfiguracion(): Configuracion {
  const { data } = useQuery({
    queryKey: ["configuracion"],
    queryFn: cargarConfiguracion,
    staleTime: Infinity,
  });
  return data ?? actual;
}
