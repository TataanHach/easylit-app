# Prueba de despliegue · Render + Neon + Cloudflare R2 + Firebase

```
Navegador ──▶ easylit-web (Render, React)
                 │  inicia sesión con Firebase y llama a la API con su token
                 ▼
              easylit-api (Render: Django + Celery en el mismo servicio)
                 ├──▶ easylit-redis (Render Key Value: cola de Celery)
                 ├──▶ Neon (PostgreSQL: datos)
                 ├──▶ Cloudflare R2 (archivos: Excel subidos y generados)
                 └──▶ Firebase (verifica tokens y crea cuentas de invitados)
```

Todo en planes gratuitos. Los nombres de botones de cada panel pueden variar un
poco; la idea de cada paso es la misma.

> En tu PC no cambia nada: sin estas variables la app sigue usando el login
> propio y la carpeta `media/`.

---

## 1. Neon (base de datos)

1. Crea una cuenta en neon.tech → **New Project** (región: la más cercana a
   Oregon, ej. *US West*).
2. En **Connection Details** copia la *connection string*. Se ve así:
   `postgresql://usuario:clave@ep-xxxx.us-west-2.aws.neon.tech/neondb?sslmode=require`
3. Guárdala: es `DATABASE_URL`.

## 2. Cloudflare R2 (archivos)

1. En el panel de Cloudflare → **R2 Object Storage** → **Create bucket**.
   Nombre: `easylit-archivos`. Déjalo **privado** (sin acceso público).
2. **Manage R2 API Tokens** → **Create API token** → permiso
   *Object Read & Write*, limitado al bucket `easylit-archivos`.
3. Al crearlo, copia (solo se muestran una vez):
   - **Access Key ID** → `R2_ACCESS_KEY_ID`
   - **Secret Access Key** → `R2_SECRET_ACCESS_KEY`
   - **Endpoint** (`https://<id-de-cuenta>.r2.cloudflarestorage.com`) → `R2_ENDPOINT`
4. `R2_BUCKET` = `easylit-archivos`.

Las descargas pasan por la API (que revisa permisos), así que el bucket no
necesita CORS ni acceso público.

## 3. Firebase (inicio de sesión)

1. console.firebase.google.com → **Agregar proyecto** (Google Analytics: no hace falta).
2. **Authentication** → **Comenzar** → **Sign-in method** → habilita
   **Correo electrónico/contraseña**.
3. **Configuración del proyecto** (engranaje) → **Tus apps** → ícono **web `</>`**
   → registra la app (sin Hosting). Copia de `firebaseConfig`:
   - `apiKey` → `VITE_FIREBASE_API_KEY`
   - `authDomain` → `VITE_FIREBASE_AUTH_DOMAIN`
   - `projectId` → `VITE_FIREBASE_PROJECT_ID` y también `FIREBASE_PROJECT_ID`
   - `appId` → `VITE_FIREBASE_APP_ID`
4. **Configuración del proyecto** → **Cuentas de servicio** → **Generar nueva
   clave privada**. Se descarga un `.json`: su contenido completo es
   `FIREBASE_CREDENCIALES`. **Es secreto: no lo subas a git.**
5. Cuando tengas la URL de `easylit-web` (paso 4): **Authentication** →
   **Configuración** → **Dominios autorizados** → agrega
   `easylit-web.onrender.com`.

Nadie puede registrarse por su cuenta: aunque cree una cuenta en Firebase, la API
la rechaza si no fue invitada o vinculada en EasyLit.

## 4. Render (despliegue)

1. Sube los cambios a GitHub (`git push`).
2. En render.com → **New** → **Blueprint** → elige el repo `easylit-app`.
   Render lee `render.yaml` y propone 3 servicios: `easylit-redis`,
   `easylit-api` y `easylit-web`.
3. Te pedirá las variables marcadas como secretas. Para `easylit-api`:

   | Variable | Valor |
   |---|---|
   | `DATABASE_URL` | la de Neon (paso 1) |
   | `FRONTEND_URL` | `https://easylit-web.onrender.com` |
   | `GEMINI_API_KEY` | tu clave de Gemini |
   | `R2_BUCKET`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | paso 2 |
   | `FIREBASE_PROJECT_ID` | paso 3 |
   | `FIREBASE_CREDENCIALES` | el contenido completo del `.json` (paso 3.4) |

   Para `easylit-web`:

   | Variable | Valor |
   |---|---|
   | `VITE_API_URL` | `https://easylit-api.onrender.com` |
   | `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID` | paso 3.3 |

   Si Render asigna otra URL a algún servicio (por ejemplo `easylit-api-x1y2`),
   usa esa en `FRONTEND_URL` / `VITE_API_URL` y vuelve a desplegar el servicio.
4. **Apply**. El primer despliegue de la API crea las tablas en Neon
   (`build.sh` corre `migrate`).
5. Revisa `https://easylit-api.onrender.com/api/health/` → `{"status": "ok"}`.

## 5. Primer usuario (desde tu PC, contra Neon)

Como la base está en Neon, puedes crear los usuarios desde tu PC. En PowerShell,
dentro de `backend/` con el `.venv` activo:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
$env:SECRET_KEY = "cualquier-valor-local"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:DATABASE_URL = "postgresql://...neon.tech/neondb?sslmode=require"
$env:FIREBASE_PROJECT_ID = "tu-proyecto"
$env:FIREBASE_CREDENCIALES = Get-Content "C:\ruta\clave-firebase.json" -Raw

# 1. Superadmin (también sirve para entrar a /admin/)
python manage.py createsuperuser

# 2. Su cuenta de Firebase, para entrar a la app
python manage.py vincular_firebase tu@correo.cl --password "Clave#2026"
```

Luego, en `https://easylit-api.onrender.com/admin/` (con la contraseña del
superadmin) crea la **Organización** y su **Gerente**, y vincula al gerente:

```powershell
python manage.py vincular_firebase gerente@empresa.cl --password "Otra#2026"
```

El gerente entra a la app e invita a sus trabajadores como siempre: al activar
la invitación, EasyLit les crea su cuenta en Firebase.

## 6. Qué probar

- [ ] Entrar con el gerente en `https://easylit-web.onrender.com`.
- [ ] Contraseña incorrecta → aviso bajo el campo.
- [ ] Crear una plantilla (el Excel queda en R2: revísalo en el bucket).
- [ ] Nueva transformación → animación de pasos → mapeo (lo procesa Celery).
- [ ] Generar y descargar el documento.
- [ ] Invitar un trabajador, activar la invitación y entrar con él.

## Límites del plan gratis

- `easylit-api` **se duerme tras ~15 min sin uso**: el primer acceso después
  tarda alrededor de un minuto. Como Celery corre en el mismo servicio, también
  se duerme (no hay tareas pendientes en ese momento, así que no se pierde nada).
- API y Celery comparten la memoria del plan gratis (512 MB). Con archivos muy
  grandes podría quedarse corto; en ese caso, separar el worker (plan de pago):
  ver el comentario al inicio de `backend/start.sh`.
- Neon y R2 gratuitos alcanzan de sobra para una prueba.
