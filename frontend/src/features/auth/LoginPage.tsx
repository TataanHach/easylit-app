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
import { Navigate, useNavigate } from "react-router-dom";
import axios from "axios";
import { useAuth } from "./AuthContext";
import { authService } from "./authService";
import "./auth.css";
import { LIMITES, limpiarTexto } from "@/lib/limites";
import { useConfiguracion } from "@/lib/configuracion";
import { firebaseActivo } from "@/lib/firebase";
import { describirError } from "@/lib/errores";
import { problemaCorreo } from "@/lib/validar";

export default function LoginPage() {
  const { contrasena_max: CONTRASENA_MAX } = useConfiguracion();
  const { usuario, login } = useAuth();
  const navigate = useNavigate();

  const [paso, setPaso] = useState<"correo" | "password">("correo");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [verPw, setVerPw] = useState(false);
  const [error, setError] = useState("");
  // Error de un campo concreto: se muestra bajo ese campo y lo marca en rojo.
  const [errorEmail, setErrorEmail] = useState("");
  const [errorPw, setErrorPw] = useState("");
  const [cargando, setCargando] = useState(false);

  // Con la sesión abierta no tiene sentido volver a pedir el login.
  if (usuario) return <Navigate to="/" replace />;

  async function continuarConCorreo(e: FormEvent) {
    e.preventDefault();
    setError("");
    const correo = limpiarTexto(email);
    setEmail(correo);
    const problema = problemaCorreo(correo);
    setErrorEmail(problema);
    if (problema) return;
    setCargando(true);
    try {
      const estado = await authService.estadoCorreo(correo);
      if (!estado.existe) {
        setErrorEmail("Este correo no tiene una cuenta en EasyLit. Revisa que esté bien escrito o pide a tu gerente que te invite.");
      } else if (estado.necesita_contrasena) {
        // Fue invitado y aún no tiene contraseña → a crearla.
        navigate("/crear-contrasena", { state: { email: correo } });
      } else {
        setPaso("password");
      }
    } catch (err) {
      const { titulo, detalle } = describirError(err, "verificar el correo");
      setError(`${titulo}. ${detalle}`);
    } finally {
      setCargando(false);
    }
  }

  async function iniciarSesion(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!password) { setErrorPw("Escribe tu contraseña para entrar."); return; }
    setErrorPw("");
    setCargando(true);
    try {
      await login(limpiarTexto(email), password);
      navigate("/");
    } catch (err) {
      const codigo = (err as { code?: string })?.code ?? "";
      if (codigo === "auth/invalid-credential" || codigo === "auth/wrong-password") {
        setErrorPw("La contraseña no es correcta. Revisa las mayúsculas y vuelve a intentarlo.");
      } else if (!firebaseActivo && axios.isAxiosError(err) && err.response?.status === 401) {
        // Solo la contraseña puede estar mal: el correo ya se verificó en el paso 1.
        setErrorPw("La contraseña no es correcta. Revisa las mayúsculas y vuelve a intentarlo.");
      } else {
        const { titulo, detalle } = describirError(err, "iniciar sesión");
        setError(`${titulo}. ${detalle}`);
      }
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
            <form onSubmit={continuarConCorreo} noValidate>
              <div className="field">
                <label htmlFor="email">Correo electrónico</label>
                <div className="input-wrap">
                  <i className="ti ti-mail" />
                  <input
                    id="email" type="email" className={`auth-input ${errorEmail ? "error" : ""}`} autoComplete="email"
                    placeholder="nombre@empresa.cl" autoFocus maxLength={LIMITES.email}
                    aria-invalid={!!errorEmail} aria-describedby={errorEmail ? "email-error" : undefined}
                    value={email} onChange={(e) => { setEmail(e.target.value); setErrorEmail(""); }}
                    onBlur={(e) => setEmail(limpiarTexto(e.target.value))}
                  />
                </div>
                {errorEmail && <p id="email-error" className="hint error">{errorEmail}</p>}
              </div>
              <button className="auth-btn" type="submit" disabled={cargando}>
                {cargando ? "Verificando…" : <>Continuar <i className="ti ti-arrow-right" /></>}
              </button>
            </form>
          ) : (
            <form onSubmit={iniciarSesion} noValidate>
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
                    className={`auth-input has-toggle ${errorPw ? "error" : ""}`} autoComplete="current-password"
                    placeholder="Tu contraseña" autoFocus maxLength={CONTRASENA_MAX}
                    aria-invalid={!!errorPw} aria-describedby={errorPw ? "password-error" : undefined}
                    value={password} onChange={(e) => { setPassword(e.target.value); setErrorPw(""); }}
                  />
                  <button type="button" className="toggle-pw" onClick={() => setVerPw(!verPw)}
                    aria-label={verPw ? "Ocultar" : "Mostrar"}>
                    <i className={verPw ? "ti ti-eye-off" : "ti ti-eye"} />
                  </button>
                </div>
                {errorPw && <p id="password-error" className="hint error">{errorPw}</p>}
              </div>
              <button className="auth-btn" type="submit" disabled={cargando}>
                {cargando ? "Ingresando…" : <><i className="ti ti-login-2" /> Iniciar sesión</>}
              </button>
              <p className="auth-alt">
                <button type="button" onClick={() => { setPaso("correo"); setPassword(""); setError(""); setErrorPw(""); }}
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
