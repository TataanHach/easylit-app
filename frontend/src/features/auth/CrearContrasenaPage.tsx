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

function fuerza(pw: string): number {
  if (!pw) return 0;
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s++;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) s++;
  return Math.min(s, 4);
}

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

  const nivel = fuerza(password);
  const coinciden = password2.length > 0 && password === password2;
  const rutOk = rut === "" || rutValido(rut);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!coinciden) { setError("Las contraseñas no coinciden."); return; }
    if (!rutOk) { setError("El RUT no es válido."); return; }
    setCargando(true);
    try {
      await crearContrasena({ token, password, password2, rut: rut || undefined });
      navigate("/");
    } catch {
      setError("No se pudo crear la contraseña. El enlace de invitación puede haber expirado.");
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
                    placeholder="Pega aquí el código de tu invitación" required
                    value={token} onChange={(e) => setToken(e.target.value)} />
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
                  placeholder="Mínimo 8 caracteres" required
                  value={password} onChange={(e) => setPassword(e.target.value)} />
                <button type="button" className="toggle-pw" onClick={() => setVerPw(!verPw)}>
                  <i className={verPw ? "ti ti-eye-off" : "ti ti-eye"} />
                </button>
              </div>
              <div className="pw-strength" data-level={nivel}>
                <span className="pw-seg" /><span className="pw-seg" /><span className="pw-seg" /><span className="pw-seg" />
              </div>
            </div>

            <div className="field">
              <label htmlFor="pw2">Confirmar contraseña</label>
              <div className="input-wrap">
                <i className="ti ti-lock-check" />
                <input id="pw2" type={verPw ? "text" : "password"}
                  className={`auth-input ${password2 ? (coinciden ? "ok" : "error") : ""}`}
                  autoComplete="new-password" placeholder="Repite la contraseña" required
                  value={password2} onChange={(e) => setPassword2(e.target.value)} />
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
                  placeholder="12.345.678-9"
                  value={rut} onChange={(e) => setRut(formatearRut(e.target.value))} />
              </div>
              {rut && !rutOk && <p className="hint error">El dígito verificador no corresponde</p>}
            </div>

            <button className="auth-btn" type="submit" disabled={cargando || !coinciden}>
              {cargando ? "Creando…" : <><i className="ti ti-check" /> Crear contraseña y entrar</>}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
