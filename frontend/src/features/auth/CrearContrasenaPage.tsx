/**
 * Pantalla de primer ingreso: crear contraseña.
 *
 * El colaborador llega aquí con el código de invitación que le envió su gerente
 * (pantalla Equipo) y lo escribe o pega a mano. El código nunca viaja en la
 * dirección (?codigo=…): quedaría en el historial y en los registros de servidores.
 * Define su contraseña y entra directo (el RUT ya lo ingresó el gerente al invitarlo).
 */
import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import "./auth.css";
import logoSlogan from "@/assets/logo-slogan.png";
import TerminosModal from "./TerminosModal";
import { limpiarTexto, LIMITES } from "@/lib/limites";
import { requisitosContrasena } from "@/lib/contrasena";
import { useConfiguracion } from "@/lib/configuracion";
import { describirError } from "@/lib/errores";

export default function CrearContrasenaPage() {
  const cfg = useConfiguracion();
  const REQUISITOS_CONTRASENA = requisitosContrasena(cfg);
  const CONTRASENA_MIN = cfg.contrasena_min;
  const CONTRASENA_MAX = cfg.contrasena_max;
  const { crearContrasena } = useAuth();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { email?: string; token?: string } };

  const [token, setToken] = useState(location.state?.token ?? "");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [verPw, setVerPw] = useState(false);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [aceptaTerminos, setAceptaTerminos] = useState(false);
  const [verTerminos, setVerTerminos] = useState(false);
  const [faltaAceptar, setFaltaAceptar] = useState(false);

  // La barra muestra cuántos requisitos se cumplen (0 a 4).
  const nivel = password ? REQUISITOS_CONTRASENA.filter((r) => r.cumple(password)).length : 0;
  const pwOk = REQUISITOS_CONTRASENA.every((r) => r.cumple(password));
  const coinciden = password2.length > 0 && password === password2;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError("");
    const codigo = limpiarTexto(token);
    setToken(codigo);
    if (!codigo) { setError("Falta el código de invitación. Cópialo desde el mensaje que te envió tu gerente y pégalo en el primer campo."); return; }
    if (!pwOk) {
      const faltan = REQUISITOS_CONTRASENA.filter((r) => !r.cumple(password)).map((r) => r.texto.toLowerCase());
      setError(`La contraseña no cumple los requisitos. Le falta: ${faltan.join(", ")}.`);
      return;
    }
    if (!coinciden) { setError("Las contraseñas no coinciden. Escribe la misma contraseña en los dos campos."); return; }
    if (!aceptaTerminos) {
      setFaltaAceptar(true);
      setError("Para crear tu cuenta debes aceptar los términos y condiciones. Marca la casilla de abajo.");
      return;
    }
    setCargando(true);
    try {
      await crearContrasena({ token: codigo, password, password2 });
      navigate("/");
    } catch (e) {
      const { titulo, detalle } = describirError(e, "crear la contraseña");
      setError(`${titulo}. ${detalle}`);
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="auth-wrap">
      <aside className="auth-brand">
        <div className="auth-brand-top">
          <span className="auth-logo"><img src="/favicon-192.png" alt="" /></span>
          <div>
            <div className="auth-brand-name">EasyLit</div>
            <div className="auth-brand-sub">v2.5 · Beta</div>
          </div>
        </div>
        <div className="auth-brand-mid">
          <h2>Bienvenido al equipo.</h2>
          <p>Define tu contraseña para acceder. La usarás junto con tu correo cada vez que entres.</p>
        </div>
        <p className="auth-brand-foot">© 2026 EasyLit · Concepción, Chile</p>
      </aside>

      <main className="auth-form-col">
        <div className="auth-card">
          <img
            className="auth-logo-slogan"
            src={logoSlogan}
            alt="EasyLit · Tú defines el formato, EasyLit lo transforma para ti"
            width={900}
            height={288}
          />
          <div className="auth-head">
            <h1>Crea tu contraseña</h1>
            <p>Es tu primer ingreso. Define una contraseña segura.</p>
          </div>

          {error && (
            <div className="auth-error">
              <i aria-hidden="true" className="ti ti-alert-circle" /><span>{error}</span>
            </div>
          )}

          <form onSubmit={enviar} noValidate>
            {!location.state?.token && (
              <div className="field">
                <label htmlFor="token">Código de invitación</label>
                <div className="input-wrap">
                  <i aria-hidden="true" className="ti ti-key" />
                  <input id="token" type="text" className="auth-input"
                    placeholder="Ej: K7M2-QX9P" maxLength={LIMITES.tokenInvitacion}
                    value={token} onChange={(e) => setToken(e.target.value)}
                    onBlur={(e) => setToken(limpiarTexto(e.target.value).toUpperCase())} />
                </div>
                <p className="hint">Te lo envía tu gerente desde la pantalla Equipo de EasyLit.</p>
              </div>
            )}

            <div className="field">
              <label htmlFor="pw">Contraseña</label>
              <div className="input-wrap">
                <i aria-hidden="true" className="ti ti-lock" />
                <input id="pw" type={verPw ? "text" : "password"}
                  className="auth-input has-toggle" autoComplete="new-password"
                  placeholder={`Entre ${CONTRASENA_MIN} y ${CONTRASENA_MAX} caracteres`} maxLength={CONTRASENA_MAX}
                  value={password} onChange={(e) => setPassword(e.target.value)} />
                <button type="button" className="toggle-pw" onClick={() => setVerPw(!verPw)}
                  aria-label={verPw ? "Ocultar contraseña" : "Mostrar contraseña"}>
                  <i aria-hidden="true" className={verPw ? "ti ti-eye-off" : "ti ti-eye"} />
                </button>
              </div>
              <div className="pw-strength" data-level={nivel}>
                <span className="pw-seg" /><span className="pw-seg" /><span className="pw-seg" /><span className="pw-seg" />
              </div>
              <ul className="pw-requisitos" aria-label="Requisitos de la contraseña">
                {REQUISITOS_CONTRASENA.map((r) => {
                  const ok = r.cumple(password);
                  return (
                    <li key={r.texto} className={ok ? "ok" : password ? "falta" : ""}>
                      <i aria-hidden="true" className={ok ? "ti ti-circle-check" : "ti ti-circle"} /> {r.texto}
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className="field">
              <label htmlFor="pw2">Confirmar contraseña</label>
              <div className="input-wrap">
                <i aria-hidden="true" className="ti ti-lock-check" />
                <input id="pw2" type={verPw ? "text" : "password"}
                  className={`auth-input ${password2 ? (coinciden ? "ok" : "error") : ""}`}
                  autoComplete="new-password" placeholder="Repite la contraseña"
                  maxLength={CONTRASENA_MAX} value={password2} onChange={(e) => setPassword2(e.target.value)} />
              </div>
              {password2 && (
                <p className={`hint ${coinciden ? "ok" : "error"}`}>
                  {coinciden ? "Las contraseñas coinciden" : "Las contraseñas no coinciden"}
                </p>
              )}
            </div>

            <div className={`terminos-check ${faltaAceptar && !aceptaTerminos ? "error" : ""}`}>
              <input id="terminos" type="checkbox" checked={aceptaTerminos}
                onChange={(e) => { setAceptaTerminos(e.target.checked); setFaltaAceptar(false); }} />
              <label htmlFor="terminos">
                Acepto los{" "}
                <button type="button" className="terminos-link" onClick={() => setVerTerminos(true)}>
                  términos y condiciones
                </button>{" "}
                de uso de EasyLit.
              </label>
            </div>

            <button className="auth-btn" type="submit" disabled={cargando}>
              {cargando ? "Creando…" : <><i aria-hidden="true" className="ti ti-check" /> Crear contraseña y entrar</>}
            </button>
          </form>
        </div>
      </main>

      {verTerminos && (
        <TerminosModal
          onCerrar={() => setVerTerminos(false)}
          onAceptar={() => { setAceptaTerminos(true); setFaltaAceptar(false); setVerTerminos(false); }}
        />
      )}
    </div>
  );
}
