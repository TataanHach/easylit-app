/**
 * Tipos del dominio, en espejo con los modelos de Django.
 *
 * Mantener estos tipos alineados con el backend es lo que hace que TypeScript
 * atrape errores en el editor de mapeo antes de que lleguen al usuario.
 */

export type Rol = "SUPERADMIN" | "GERENTE" | "TRABAJADOR";

export type EstadoTransformacion =
  | "BORRADOR"
  | "LIMPIEZA"
  | "MAPEO_PROPUESTO"
  | "EN_REVISION"
  | "APROBADO"
  | "GENERADO"
  | "ERROR";

export interface Usuario {
  id: string;
  email: string;
  nombre_completo: string;
  rut: string;
  telefono: string;
  rol: Rol;
  organizacion: string | null;
  organizacion_nombre: string | null;
  necesita_crear_contrasena: boolean;
}

export interface Organizacion {
  id: string;
  nombre: string;
  rut: string;
  anonimizar_montos: boolean;
}

export interface CampoPlantilla {
  id: string;
  nombre: string;
  tipo: "TEXTO" | "NUMERO" | "MONEDA" | "FECHA" | "UNIDAD";
  obligatorio: boolean;
  moneda_destino: string;
  descripcion: string;
}

export interface Plantilla {
  id: string;
  nombre: string;
  mandante: string;
  sector: string;
  formato: "XLSX" | "CSV" | "PDF" | "DOCX";
  total_campos: number;
  favorita: boolean;
  usos: number;
  campos?: CampoPlantilla[];
}

export interface MapeoCampo {
  id: string;
  origen_columna: string;
  origen_muestra: string[];
  destino_campo: string | null;
  confianza: number;
  motivo: string;
  ajustado_por_humano: boolean;
}

export interface Partida {
  id: string;
  codigo: string;
  capitulo: string;
  es_capitulo: boolean;
  descripcion: string;
  unidad_origen: string;
  unidad_canonica: string | null;
  cantidad: number | null;
  precio_unitario: number | null;
  total: number | null;
  requiere_revision: boolean;
}

export interface Transformacion {
  id: string;
  nombre_origen: string;
  mandante: string;
  plantilla: string;
  plantilla_nombre?: string;
  estado: EstadoTransformacion;
  detalle_error?: string;
  confianza: number | null;
  autor: string;
  autor_nombre?: string;
  descargable: boolean;
  creada: string;
  mapeos?: MapeoCampo[];
  resultado_limpieza?: Record<string, number>;
}
