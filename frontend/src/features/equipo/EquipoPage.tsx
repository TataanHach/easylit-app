/**
 * Pantalla Equipo (solo gerente).
 *
 * Lista a las personas de la organización con el estado de su acceso, permite
 * invitar colaboradores y generar su código de invitación. El código se crea
 * aquí, se muestra una sola vez (en la base solo queda su huella) y el gerente
 * se lo envía al colaborador: EasyLit no manda correos.
 */
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/AuthContext";
import { useAvisos } from "@/components/ui/Avisos";
import { describirError } from "@/lib/errores";
import { formatearRut } from "@/lib/rut";
import { equipoService, type CodigoInvitacion, type EstadoAcceso, type MiembroEquipo } from "./equipoService";
import InvitarModal from "./InvitarModal";
import CodigoModal from "./CodigoModal";
import "@/features/historial/historial.css";
import "@/features/plantillas/plantillas.css";
import "./equipo.css";

const ESTADOS: Record<EstadoAcceso, { clase: string; icono: string; texto: string; ayuda: string }> = {
  ACTIVO: { clase: "done", icono: "ti ti-circle-check", texto: "Activo", ayuda: "Ya creó su contraseña y puede entrar." },
  PENDIENTE: { clase: "review", icono: "ti ti-clock", texto: "Pendiente", ayuda: "Tiene un código vigente; aún no crea su contraseña. Si lo perdió, genera uno nuevo." },
  VENCIDA: { clase: "error", icono: "ti ti-clock-x", texto: "Código vencido", ayuda: "Su código ya no sirve. Genera uno nuevo." },
  SIN_INVITACION: { clase: "draft", icono: "ti ti-key-off", texto: "Sin código", ayuda: "Se creó sin código de invitación. Genera uno para que pueda entrar." },
  DESACTIVADO: { clase: "draft", icono: "ti ti-ban", texto: "Desactivado", ayuda: "Un administrador le quitó el acceso." },
};

const ROLES: Record<string, string> = { GERENTE: "Gerente", TRABAJADOR: "Trabajador", SUPERADMIN: "Superadministrador" };

export default function EquipoPage() {
  const { usuario } = useAuth();
  const avisos = useAvisos();
  const queryClient = useQueryClient();
  const esGerente = usuario?.rol === "GERENTE";

  const [invitando, setInvitando] = useState(false);
  const [codigo, setCodigo] = useState<{ nombre: string; inv: CodigoInvitacion } | null>(null);
  const [generando, setGenerando] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["equipo"],
    queryFn: equipoService.listar,
    enabled: esGerente,
    refetchOnMount: "always",
  });

  const recargar = () => queryClient.invalidateQueries({ queryKey: ["equipo"] });

  function trasInvitar(nombre: string, inv: CodigoInvitacion) {
    setInvitando(false);
    setCodigo({ nombre, inv });
    recargar();
  }

  async function generarCodigo(m: MiembroEquipo) {
    setGenerando(m.id);
    try {
      const inv = await equipoService.nuevoCodigo(m.id);
      setCodigo({ nombre: m.nombre_completo, inv });
      recargar();
    } catch (e) {
      avisos.error(describirError(e, "generar el código"));
    } finally {
      setGenerando(null);
    }
  }

  if (!esGerente) {
    return (
      <div className="estado-caja">
        <i aria-hidden="true" className="ti ti-lock" />
        <h3>Solo para gerentes</h3>
        <p>Si necesitas sumar a alguien a EasyLit, pídeselo al gerente de tu empresa.</p>
      </div>
    );
  }

  const pendientes = data?.filter((m) => m.estado !== "ACTIVO" && m.estado !== "DESACTIVADO").length ?? 0;

  return (
    <>
      <div className="page-header eq-header">
        <div>
          <h1>Equipo</h1>
          <p>Las personas de {usuario?.organizacion_nombre ?? "tu empresa"} que usan EasyLit. Invita a un colaborador y envíale su código para que cree su contraseña.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setInvitando(true)}>
          <i aria-hidden="true" className="ti ti-user-plus" /> Invitar colaborador
        </button>
      </div>

      <div className="panel">
        <div className="panel-head">
          <span className="panel-title">
            Personas
            {data && <span className="panel-count">{data.length}{pendientes > 0 ? ` · ${pendientes} sin activar` : ""}</span>}
          </span>
        </div>

        {isLoading && (
          <div className="estado-caja">
            <i aria-hidden="true" className="ti ti-loader-2" /><p style={{ marginTop: 8 }}>Cargando…</p>
          </div>
        )}

        {isError && (
          <div className="estado-caja">
            <i aria-hidden="true" className="ti ti-alert-circle" style={{ color: "var(--danger-500)" }} />
            <h3>No se pudo cargar el equipo</h3>
            <p>No hay conexión con el servidor. Revisa tu internet y recarga la página.</p>
          </div>
        )}

        {data && data.length <= 1 && (
          <div className="estado-caja">
            <i aria-hidden="true" className="ti ti-users" />
            <h3>Aún no hay colaboradores</h3>
            <p>Invita al primero con el botón «Invitar colaborador».</p>
          </div>
        )}

        {data && data.length > 1 && (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Correo</th>
                  <th>RUT</th>
                  <th>Rol</th>
                  <th>Estado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.map((m) => (
                  <Fila key={m.id} m={m} esYo={m.id === usuario?.id} generando={generando === m.id}
                    onGenerar={() => generarCodigo(m)} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {invitando && <InvitarModal onCerrar={() => setInvitando(false)} onInvitado={trasInvitar} />}
      {codigo && (
        <CodigoModal nombre={codigo.nombre} organizacion={usuario?.organizacion_nombre ?? null}
          inv={codigo.inv} onCerrar={() => setCodigo(null)} />
      )}
    </>
  );
}

function Fila({ m, esYo, generando, onGenerar }: {
  m: MiembroEquipo; esYo: boolean; generando: boolean; onGenerar: () => void;
}) {
  const e = ESTADOS[m.estado];
  const iniciales = m.nombre_completo.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return (
    <tr>
      <td>
        <span className={`owner-cell ${esYo ? "yo" : ""}`}>
          <span className="avatar-mini">{iniciales}</span>
          {m.nombre_completo}
          {esYo && <span className="you-tag">Tú</span>}
        </span>
      </td>
      <td className="eq-correo">{m.email}</td>
      <td className="eq-rut">{m.rut ? formatearRut(m.rut) : "—"}</td>
      <td>{ROLES[m.rol] ?? m.rol}</td>
      <td><span className={`pill ${e.clase}`} title={e.ayuda}><i aria-hidden="true" className={e.icono} /> {e.texto}</span></td>
      <td className="eq-accion">
        {/* El código no se puede volver a ver (solo se guarda su huella): si el
            colaborador lo perdió, se genera uno nuevo y el anterior deja de servir. */}
        {(m.estado === "PENDIENTE" || m.estado === "VENCIDA" || m.estado === "SIN_INVITACION") && (
          <button className="btn" onClick={onGenerar} disabled={generando}
            aria-label={`Generar un código nuevo para ${m.nombre_completo}`}>
            <i aria-hidden="true" className="ti ti-refresh" /> {generando ? "Generando…" : m.estado === "PENDIENTE" ? "Nuevo código" : "Generar código"}
          </button>
        )}
      </td>
    </tr>
  );
}
