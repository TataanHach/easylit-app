# Prueba de despliegue · Render + Cloudflare R2 + Firebase

```
Navegador ──▶ easylit-web (Render, React)
                 │  inicia sesión con Firebase y llama a la API con su token
                 ▼
              easylit-api (Render: Django + Celery en el mismo servicio)
                 ├──▶ easylit-redis (Render Key Value: cola de Celery)
                 ├──▶ easylit-db (Render PostgreSQL: datos)
                 ├──▶ Cloudflare R2 (archivos: Excel subidos y generados)
                 └──▶ Firebase (verifica tokens y crea cuentas de invitados)
```

Todo en planes gratuitos. Los nombres de botones de cada panel pueden variar un
poco; la idea de cada paso es la misma.

> En tu PC no cambia nada: sin estas variables la app sigue usando el login
> propio y la carpeta `media/`.

> ⚠️ **La base de datos gratis de Render vence a los 30 días** de creada. Después
> hay unos 14 días para pasarla a un plan de pago; si no, **se borra con todos los
> datos** (usuarios, plantillas, historial; los Excel en R2 quedan, pero sin nada
> que los referencie). Anota la fecha. Si la app debe seguir viva más tiempo
> (por ejemplo, para la defensa), antes de que venza: pasa a un plan de pago, o
> copia los datos a otra base (`pg_dump` → `pg_restore`) y cambia `DATABASE_URL`.

---

## 1. Cloudflare R2 (archivos)

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

## 2. Firebase (inicio de sesión)

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
5. Cuando tengas la URL de `easylit-web` (paso 3): **Authentication** →
   **Configuración** → **Dominios autorizados** → agrega
   `easylit-web.onrender.com`.

Nadie puede registrarse por su cuenta: aunque cree una cuenta en Firebase, la API
la rechaza si no fue invitada o vinculada en EasyLit.

## 3. Render (despliegue)

1. Sube los cambios a GitHub (`git push`).
2. En render.com → **New** → **Blueprint** → elige el repo `easylit-app`.
   Render lee `render.yaml` y propone: la base `easylit-db`, `easylit-redis`,
   `easylit-api` y `easylit-web`. La base se conecta sola a la API
   (`DATABASE_URL` no se pega a mano).
3. Te pedirá las variables marcadas como secretas. Para `easylit-api`:

   | Variable | Valor |
   |---|---|
   | `FRONTEND_URL` | `https://easylit-web.onrender.com` |
   | `GEMINI_API_KEY` | tu clave de Gemini |
   | `R2_BUCKET`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | paso 1 |
   | `FIREBASE_PROJECT_ID` | paso 2 |
   | `FIREBASE_CREDENCIALES` | el contenido completo del `.json` (paso 2.4) |

   Para `easylit-web`:

   | Variable | Valor |
   |---|---|
   | `VITE_API_URL` | `https://easylit-api.onrender.com` |
   | `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID` | paso 2.3 |

   Si Render asigna otra URL a algún servicio (por ejemplo `easylit-api-x1y2`),
   usa esa en `FRONTEND_URL` / `VITE_API_URL` y vuelve a desplegar el servicio.
4. **Apply**. El primer despliegue de la API crea las tablas en la base
   (`build.sh` corre `migrate`).
5. Revisa `https://easylit-api.onrender.com/api/health/` → `{"status": "ok"}`.

## 4. Primer usuario (desde tu PC, contra la base de Render)

El plan gratis no tiene consola (Shell), así que los primeros usuarios se crean
desde tu PC. En Render → `easylit-db` → **Connect** → pestaña **External**, copia
la **External Database URL** (termina en `.oregon-postgres.render.com/easylit`).
Luego, en PowerShell, dentro de `backend/` con el `.venv` activo:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
$env:SECRET_KEY = "cualquier-valor-local"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:DATABASE_URL = "postgresql://easylit:...@dpg-xxxx-a.oregon-postgres.render.com/easylit"
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

## 5. Qué probar

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
- La base gratis: 1 GB y **vence a los 30 días** (ver aviso al inicio). No
  tiene copias de seguridad automáticas.
- R2 gratis (10 GB) alcanza de sobra para una prueba.
