/**
 * Pantalla de primer ingreso: crear contraseña.
 *
 * El trabajador llega aquí con el token de la invitación (por ahora, en
 * desarrollo, se puede pegar a mano; en producción viaja en el enlace del
 * correo). Define su contraseña, opcionalmente su RUT, y entra directo.
 */
import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { formatearRut, rutValido } from "@/lib/rut";
import "./auth.css";
import { limpiarTexto, LIMITES } from "@/lib/limites";
import { CONTRASENA_MAX, CONTRASENA_MIN, REQUISITOS_CONTRASENA, contrasenaValida } from "@/lib/contrasena";
import { describirError } from "@/lib/errores";

export default function CrearContrasenaPage() {
  const { crearContrasena } = useAuth();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { email?: string; token?: string } };

  const [token, setToken] = useState(location.state?.token ?? "");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [rut, setRut] = useState("");
  const [verPw, setVerPw] = useState(false);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  // La barra muestra cuántos requisitos se cumplen (0 a 4).
  const nivel = password ? REQUISITOS_CONTRASENA.filter((r) => r.cumple(password)).length : 0;
  const pwOk = contrasenaValida(password);
  const coinciden = password2.length > 0 && password === password2;
  const rutOk = rut === "" || rutValido(rut);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!pwOk) {
      const faltan = REQUISITOS_CONTRASENA.filter((r) => !r.cumple(password)).map((r) => r.texto.toLowerCase());
      setError(`La contraseña no cumple los requisitos. Le falta: ${faltan.join(", ")}.`);
      return;
    }
    if (!coinciden) { setError("Las contraseñas no coinciden. Escribe la misma contraseña en los dos campos."); return; }
    if (!rutOk) { setError("El RUT no es válido: el dígito verificador no corresponde. Revísalo o deja el campo vacío."); return; }
    setCargando(true);
    try {
      await crearContrasena({ token: limpiarTexto(token), password, password2, rut: limpiarTexto(rut) || undefined });
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
          <span className="auth-logo"><i className="ti ti-file-invoice" /></span>
          <div>
            <div className="auth-brand-name">EasyLit</div>
            <div className="auth-brand-sub">v1.0 · Beta</div>
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
          <div className="auth-head">
            <h1>Crea tu contraseña</h1>
            <p>Es tu primer ingreso. Define una contraseña segura.</p>
          </div>

          {error && (
            <div className="auth-error">
              <i className="ti ti-alert-circle" /><span>{error}</span>
            </div>
          )}

          <form onSubmit={enviar}>
            {!location.state?.token && (
              <div className="field">
                <label htmlFor="token">Código de invitación</label>
                <div className="input-wrap">
                  <i className="ti ti-key" />
                  <input id="token" type="text" className="auth-input"
                    placeholder="Pega aquí el código de tu invitación" required maxLength={LIMITES.tokenInvitacion}
                    value={token} onChange={(e) => setToken(e.target.value)}
                    onBlur={(e) => setToken(limpiarTexto(e.target.value))} />
                </div>
                <p className="hint">En desarrollo, este código lo entrega el endpoint de invitación.</p>
              </div>
            )}

            <div className="field">
              <label htmlFor="pw">Contraseña</label>
              <div className="input-wrap">
                <i className="ti ti-lock" />
                <input id="pw" type={verPw ? "text" : "password"}
                  className="auth-input has-toggle" autoComplete="new-password"
                  placeholder="Entre 6 y 18 caracteres" required minLength={CONTRASENA_MIN} maxLength={CONTRASENA_MAX}
                  value={password} onChange={(e) => setPassword(e.target.value)} />
                <button type="button" className="toggle-pw" onClick={() => setVerPw(!verPw)}>
                  <i className={verPw ? "ti ti-eye-off" : "ti ti-eye"} />
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
                      <i className={ok ? "ti ti-circle-check" : "ti ti-circle"} /> {r.texto}
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className="field">
              <label htmlFor="pw2">Confirmar contraseña</label>
              <div className="input-wrap">
                <i className="ti ti-lock-check" />
                <input id="pw2" type={verPw ? "text" : "password"}
                  className={`auth-input ${password2 ? (coinciden ? "ok" : "error") : ""}`}
                  autoComplete="new-password" placeholder="Repite la contraseña" required
                  minLength={CONTRASENA_MIN} maxLength={CONTRASENA_MAX} value={password2} onChange={(e) => setPassword2(e.target.value)} />
              </div>
              {password2 && (
                <p className={`hint ${coinciden ? "ok" : "error"}`}>
                  {coinciden ? "Las contraseñas coinciden" : "Las contraseñas no coinciden"}
                </p>
              )}
            </div>

            <div className="field">
              <label htmlFor="rut">RUT (opcional)</label>
              <div className="input-wrap">
                <i className="ti ti-id" />
                <input id="rut" type="text"
                  className={`auth-input ${rut ? (rutOk ? "ok" : "error") : ""}`}
                  placeholder="12.345.678-9" maxLength={LIMITES.rut}
                  value={rut} onChange={(e) => setRut(formatearRut(e.target.value))} />
              </div>
              {rut && !rutOk && <p className="hint error">El dígito verificador no corresponde</p>}
            </div>

            <button className="auth-btn" type="submit" disabled={cargando || !coinciden || !pwOk}>
              {cargando ? "Creando…" : <><i className="ti ti-check" /> Crear contraseña y entrar</>}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
