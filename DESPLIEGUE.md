# Despliegue en Render · EasyLit v3.2

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

> ⚠️ **La base de datos gratis de Render vence a los 30 días** de creada. Después
> hay unos 14 días para pasarla a un plan de pago; si no, **se borra con todos los
> datos** (usuarios, plantillas, historial; los Excel en R2 quedan, pero sin nada
> que los referencie). Anota la fecha. Si la app debe seguir viva más tiempo
> (por ejemplo, para la defensa), pásala a un plan de pago antes de que venza.

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
   `FIREBASE_CREDENCIALES`. **Es secreto: no lo subas a git ni lo compartas.**
   El `project_id` de ese archivo debe ser el mismo de `FIREBASE_PROJECT_ID`.
5. Cuando tengas la URL de `easylit-web` (paso 3): **Authentication** →
   **Configuración** → **Dominios autorizados** → agrega esa URL
   (por ejemplo `easylit-web-xxxx.onrender.com`).

Nadie puede registrarse por su cuenta: aunque cree una cuenta en Firebase, la API
la rechaza si no fue invitada o vinculada en EasyLit.

## 3. Render (despliegue)

1. Sube los cambios a GitHub (`git push`).
2. En render.com → **New** → **Blueprint** → elige el repo `easylit-app`.
   Render lee `render.yaml` y propone: la base `easylit-db`, `easylit-redis`,
   `easylit-api` y `easylit-web`. La base y Redis se conectan solos a la API
   (`DATABASE_URL` y `REDIS_URL` no se pegan a mano), y `SECRET_KEY` la genera
   Render.
3. Te pedirá las variables secretas. **Usa las URLs reales que Render asigna** a
   cada servicio (suelen llevar un sufijo, como `easylit-web-a1b2.onrender.com`),
   siempre con `https://` y **sin `/` al final**.

   Para `easylit-api`:

   | Variable | Valor |
   |---|---|
   | `FRONTEND_URL` | URL de `easylit-web`, ej. `https://easylit-web-a1b2.onrender.com` |
   | `GEMINI_API_KEY` | tu clave de Gemini (aistudio.google.com/apikey) |
   | `R2_BUCKET`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | paso 1 |
   | `FIREBASE_PROJECT_ID` | paso 2 |
   | `FIREBASE_CREDENCIALES` | el contenido completo del `.json` (paso 2.4) |

   Para `easylit-web`:

   | Variable | Valor |
   |---|---|
   | `VITE_API_URL` | URL de `easylit-api`, sin `/api` |
   | `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID` | paso 2.3 |
   | `VITE_SOPORTE_CORREO` | correo de soporte (burbuja y footer) |
   | `VITE_SOPORTE_WHATSAPP` | WhatsApp de soporte, con código de país y solo números (ej. `56912345678`) |

   Las variables `VITE_*` se meten en la página al compilarla: **si cambias una,
   vuelve a desplegar `easylit-web`** (Manual Deploy → *Clear build cache & deploy*).
4. **Apply**. El primer despliegue de la API crea las tablas en la base
   (`build.sh` corre `migrate`).
5. Revisa `https://<url-de-easylit-api>/api/health/` → `{"status": "ok"}`.

### Variables opcionales de `easylit-api`

| Variable | Por defecto | Para qué |
|---|---|---|
| `ARCHIVO_MAX_MB` | `20` | Peso máximo de los archivos |
| `INVITACION_DIAS_VIGENCIA` | `7` | Días que dura un código de invitación |
| `LIMITE_CREAR_CONTRASENA` | `20/hour` | Intentos en «Crear contraseña» por IP |
| `LIMITE_ESTADO_CORREO` | `30/minute` | Intentos de revisar un correo por IP |
| `LIMITE_LOGIN_IP`, `LIMITE_LOGIN_CUENTA` | `10/minute`, `20/hour` | Login propio (si no se usa Firebase) |
| `NUM_PROXIES` | `1` | Proxies delante de la API, para leer la IP real del visitante |

## 4. Primer usuario (una sola vez)

El plan gratis de Render no tiene consola (Shell), así que el primer
superadministrador se crea **una sola vez**, ejecutando los comandos de Django
contra la base de Render. Si tienes un plan de pago, puedes correrlos en
`easylit-api` → **Shell**.

En Render → `easylit-db` → **Connect** → pestaña **External**, copia la
**External Database URL**. Luego, en la carpeta `backend` del repositorio (con
sus dependencias instaladas):

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
$env:SECRET_KEY = "cualquier-valor"
$env:REDIS_URL = "redis://sin-uso:6379/0"
$env:DATABASE_URL = "<External Database URL de easylit-db>"
$env:FIREBASE_PROJECT_ID = "<tu-proyecto>"
$env:FIREBASE_CREDENCIALES = Get-Content "C:\ruta\completa\clave-firebase.json" -Raw

# Superadmin (para entrar a /admin/)
python manage.py createsuperuser

# Opcional: su cuenta de Firebase, solo si el superadmin también usará la app
python manage.py vincular_firebase tu@correo.cl --password "Clave#2026"
```

Lo demás se hace desde el panel, sin comandos. En
`https://<url-de-easylit-api>/admin/` (con la contraseña del superadmin):

1. **Organizaciones → Añadir**: crea la empresa.
2. **Usuarios → Añadir**: correo, nombre, rol **Gerente**, la organización y, en
   «Cómo entrará», **Con código de invitación**. Al guardar, arriba aparece su
   **código** (ej. `K7M2-QX9P`): cópialo, porque no se vuelve a mostrar.
3. Envíale el código al gerente. Él entra a la app, escribe su correo, pega el
   código y crea su contraseña; EasyLit le crea su cuenta de Firebase.

Si el código se pierde o vence: **Usuarios** → marca a la persona → acción
**«Generar código de invitación»** → **Ir**. El anterior deja de servir.

Desde ahí, el gerente invita a su equipo en la app: **Equipo → Invitar
colaborador**.

## 5. Qué probar

- [ ] Entrar con el gerente en la URL de `easylit-web`.
- [ ] Contraseña incorrecta → aviso bajo el campo.
- [ ] Crear una plantilla (el Excel queda en R2: revísalo en el bucket).
- [ ] Nueva transformación → animación de pasos → mapeo (lo procesa Celery).
      En la revisión **no** debe aparecer el aviso «La IA no estuvo disponible».
- [ ] Generar y descargar el documento.
- [ ] Invitar un colaborador, crear su contraseña con el código y entrar con él.
- [ ] La burbuja «¿Necesitas soporte?» y el footer muestran el correo de soporte.

## 6. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| Build de la API falla con `corsheaders.E014 ... should not have path` | `FRONTEND_URL` termina en `/` | Quita la `/` final |
| «No se pudo verificar el correo. No hay conexión con el servidor» | `VITE_API_URL` mal escrita, de otra cuenta o sin redesplegar; o `FRONTEND_URL` no calza con la URL de la app | Corrige la variable y vuelve a desplegar `easylit-web` |
| El usuario existe pero no puede entrar | Se creó en `/admin/` «Con contraseña», sin cuenta de Firebase | En **Usuarios**, acción «Generar código de invitación» (paso 4) y que cree su contraseña con el código |
| `vincular_firebase` da `INSUFFICIENT_PERMISSION` | `FIREBASE_PROJECT_ID` no es el proyecto del `.json` | Usa el `project_id` que trae el `.json` |
| El login de Firebase se bloquea en la URL nueva | Falta la URL en **Dominios autorizados** | Agrégala en Firebase (paso 2.5) |
| Aviso «La IA no estuvo disponible» y en los logs `InvalidHeader ... \n` | La clave de Gemini quedó con un salto de línea al pegarla | Borra la variable, créala de nuevo y pega la clave sin espacios ni Enter |
| Aviso «La IA no estuvo disponible» con `Gemini respondió 404` | El modelo de `IA_MODEL` ya no existe | Usa `models/gemini-3.5-flash-lite` |
| La burbuja y el footer no muestran el correo | Falta `VITE_SOPORTE_CORREO` o no se redesplegó | Agrégala y vuelve a desplegar `easylit-web` |
| «Hiciste demasiados intentos seguidos» | Límite de intentos | Esperar los minutos que indica el aviso |

Para ver el motivo de un error, Render → `easylit-api` → **Logs**, y busca el
texto del aviso (por ejemplo `Gemini respondió`).

## Límites del plan gratis

- `easylit-api` **se duerme tras ~15 min sin uso**: el primer acceso después
  tarda alrededor de un minuto. Como Celery corre en el mismo servicio, también
  se duerme (no hay tareas pendientes en ese momento, así que no se pierde nada).
- API y Celery comparten la memoria del plan gratis (512 MB). Con archivos muy
  grandes podría quedarse corto; en ese caso, separar el worker (plan de pago):
  ver el comentario al inicio de `backend/start.sh`.
- Los contadores de los límites de intentos viven en la memoria del servidor:
  se reinician cuando el servicio se duerme o se vuelve a desplegar.
- La base gratis: 1 GB y **vence a los 30 días** (ver aviso al inicio). No
  tiene copias de seguridad automáticas.
- R2 gratis (10 GB) alcanza de sobra para una prueba.
