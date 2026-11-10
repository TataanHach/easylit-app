/**
 * Modal para invitar a un trabajador: nombre, correo y RUT (los tres obligatorios).
 * Al guardar, el backend crea a la persona sin contraseña y devuelve su código;
 * la pantalla Equipo lo muestra enseguida para copiarlo.
 */
import { FormEvent, useEffect, useState } from "react";
import { equipoService, type CodigoInvitacion } from "./equipoService";
import { LIMITES, limpiarTexto } from "@/lib/limites";
import { formatearRut, rutValido } from "@/lib/rut";
import { describirError } from "@/lib/errores";

interface Props {
  onCerrar: () => void;
  onInvitado: (nombre: string, inv: CodigoInvitacion) => void;
}

export default function InvitarModal({ onCerrar, onInvitado }: Props) {
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [rut, setRut] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setError("");
    const datos = {
      nombre_completo: limpiarTexto(nombre).replace(/\s+/g, " "),
      email: limpiarTexto(email).toLowerCase(),
      rut: limpiarTexto(rut),
    };
    setNombre(datos.nombre_completo); setEmail(datos.email);
    if (!datos.nombre_completo) { setError("Falta el nombre. Escribe el nombre y apellido del trabajador."); return; }
    if (!datos.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(datos.email)) {
      setError("Falta el correo o no es válido. Escríbelo como nombre@empresa.cl."); return;
    }
    if (!datos.rut) { setError("Falta el RUT del trabajador. Escríbelo como 12.345.678-9."); return; }
    if (!rutValido(datos.rut)) { setError("El RUT no es válido: el dígito verificador no corresponde. Revísalo."); return; }

    setGuardando(true);
    let inv: CodigoInvitacion;
    try {
      inv = await equipoService.invitar(datos);
    } catch (err) {
      const { titulo, detalle } = describirError(err, "invitar al trabajador");
      setError(`${titulo}. ${detalle}`);
      setGuardando(false);
      return;
    }
    onInvitado(datos.nombre_completo, inv);
  }

  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape" && !guardando) onCerrar(); };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [guardando, onCerrar]);

  const rutMal = rut !== "" && rut.length >= 3 && !rutValido(rut);

  return (
    <div className="modal-overlay">
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="invitar-titulo">
        <div className="modal-head">
          <h2 id="invitar-titulo">Invitar trabajador</h2>
          <button className="modal-close" onClick={onCerrar} aria-label="Cerrar"><i aria-hidden="true" className="ti ti-x" /></button>
        </div>
        <form onSubmit={guardar} noValidate>
          <div className="modal-body">
            {error && <div className="modal-error" role="alert">{error}</div>}

            <div className="mfield">
              <label htmlFor="inv-nombre">Nombre completo *</label>
              <input id="inv-nombre" value={nombre} maxLength={200} autoFocus
                onChange={(e) => setNombre(e.target.value)}
                onBlur={(e) => setNombre(limpiarTexto(e.target.value))}
                placeholder="Ej. María González" />
            </div>
            <div className="mfield">
              <label htmlFor="inv-email">Correo *</label>
              <input id="inv-email" type="email" value={email} maxLength={LIMITES.email} autoComplete="off"
                onChange={(e) => setEmail(e.target.value)}
                onBlur={(e) => setEmail(limpiarTexto(e.target.value))}
                placeholder="nombre@empresa.cl" />
              <p className="mfield-ayuda">Con este correo entrará a EasyLit.</p>
            </div>
            <div className="mfield">
              <label htmlFor="inv-rut">RUT *</label>
              <input id="inv-rut" value={rut} maxLength={LIMITES.rut} aria-invalid={rutMal}
                onChange={(e) => setRut(formatearRut(e.target.value))}
                placeholder="12.345.678-9" />
              {rutMal && <p className="mfield-ayuda" style={{ color: "var(--danger-600)" }}>El dígito verificador no corresponde.</p>}
            </div>
          </div>
          <div className="modal-foot">
            <button type="button" className="btn" onClick={onCerrar}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={guardando}>
              {guardando ? "Invitando…" : <><i aria-hidden="true" className="ti ti-user-plus" /> Invitar y ver código</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
