/**
 * Pantalla de inicio de sesión.
 *
 * Flujo en dos pasos, como definimos:
 *   1. El usuario escribe su correo. Consultamos su estado.
 *   2a. Si ya tiene contraseña → mostramos el campo de contraseña.
 *   2b. Si no tiene (fue invitado) → lo mandamos a crear su contraseña.
 * Así el trabajador recién invitado no se topa con "contraseña incorrecta".
 */
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { authService } from "./authService";
import "./auth.css";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [paso, setPaso] = useState<"correo" | "password">("correo");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [verPw, setVerPw] = useState(false);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  async function continuarConCorreo(e: FormEvent) {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      const estado = await authService.estadoCorreo(email);
      if (!estado.existe) {
        setError("No hay ninguna cuenta con ese correo. Pídele a tu gerente que te dé de alta.");
      } else if (estado.necesita_contrasena) {
        // Fue invitado y aún no tiene contraseña → a crearla.
        navigate("/crear-contrasena", { state: { email } });
      } else {
        setPaso("password");
      }
    } catch {
      setError("No se pudo verificar el correo. Revisa tu conexión.");
    } finally {
      setCargando(false);
    }
  }

  async function iniciarSesion(e: FormEvent) {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      await login(email, password);
      navigate("/");
    } catch {
      setError("Correo o contraseña incorrectos.");
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
          <h2>Transforma licitaciones sin perder un solo número.</h2>
          <p>Sube el documento del mandante, limpia los datos y genera el formato exigido con el itemizado verificado partida por partida.</p>
          <ul className="auth-points">
            <li className="auth-point"><i className="ti ti-shield-lock" /> Tus precios no salen de la empresa: la IA solo ve la estructura.</li>
            <li className="auth-point"><i className="ti ti-calculator" /> Cada total se reconcilia contra el documento original.</li>
            <li className="auth-point"><i className="ti ti-history" /> Bitácora de quién cambió qué y cuándo.</li>
          </ul>
        </div>
        <p className="auth-brand-foot">© 2026 EasyLit · Concepción, Chile</p>
      </aside>

      <main className="auth-form-col">
        <div className="auth-card">
          <div className="auth-mini-logo">
            <span className="logo-icon"><i className="ti ti-file-invoice" /></span>
            <div>
              <div className="auth-brand-name">EasyLit</div>
              <div className="auth-brand-sub" style={{ color: "var(--text-3)" }}>v1.0 · Beta</div>
            </div>
          </div>

          <div className="auth-head">
            <h1>Inicia sesión</h1>
            <p>Accede a tus transformaciones y a las de tu equipo.</p>
          </div>

          {error && (
            <div className="auth-error">
              <i className="ti ti-alert-circle" />
              <span>{error}</span>
            </div>
          )}

          {paso === "correo" ? (
            <form onSubmit={continuarConCorreo}>
              <div className="field">
                <label htmlFor="email">Correo electrónico</label>
                <div className="input-wrap">
                  <i className="ti ti-mail" />
                  <input
                    id="email" type="email" className="auth-input" autoComplete="email"
                    placeholder="nombre@empresa.cl" required autoFocus
                    value={email} onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              </div>
              <button className="auth-btn" type="submit" disabled={cargando}>
                {cargando ? "Verificando…" : <>Continuar <i className="ti ti-arrow-right" /></>}
              </button>
            </form>
          ) : (
            <form onSubmit={iniciarSesion}>
              <div className="field">
                <label htmlFor="email2">Correo electrónico</label>
                <div className="input-wrap">
                  <i className="ti ti-mail" />
                  <input id="email2" type="email" className="auth-input" value={email} disabled />
                </div>
              </div>
              <div className="field">
                <label htmlFor="password">Contraseña</label>
                <div className="input-wrap">
                  <i className="ti ti-lock" />
                  <input
                    id="password" type={verPw ? "text" : "password"}
                    className="auth-input has-toggle" autoComplete="current-password"
                    placeholder="Tu contraseña" required autoFocus
                    value={password} onChange={(e) => setPassword(e.target.value)}
                  />
                  <button type="button" className="toggle-pw" onClick={() => setVerPw(!verPw)}
                    aria-label={verPw ? "Ocultar" : "Mostrar"}>
                    <i className={verPw ? "ti ti-eye-off" : "ti ti-eye"} />
                  </button>
                </div>
              </div>
              <button className="auth-btn" type="submit" disabled={cargando}>
                {cargando ? "Ingresando…" : <><i className="ti ti-login-2" /> Iniciar sesión</>}
              </button>
              <p className="auth-alt">
                <button type="button" onClick={() => { setPaso("correo"); setPassword(""); setError(""); }}
                  style={{ background: "none", border: "none", color: "var(--brand-600)", cursor: "pointer", fontWeight: 600 }}>
                  ← Usar otro correo
                </button>
              </p>
            </form>
          )}
        </div>
      </main>
    </div>
  );
}
