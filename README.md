# EasyLit

Plataforma web que transforma el Excel de una licitación (formato propio de la
empresa) al formato que exige cada mandante, con un mapeo de columnas asistido
por IA y revisado por una persona.

> **La IA propone, una persona aprueba y el código determinista aplica.**

La IA solo sugiere qué columna del archivo de origen va a cada campo de la
plantilla. Los datos los lee y limpia **pandas** con reglas fijas y los escribe
**openpyxl** en la plantilla. Los montos y cantidades nunca se envían a la IA.

Proyecto de Título — INACAP, Informática y Telecomunicaciones (TIHI84).
Equipo: Rocío Muñoz Pérez, Ernesto Quintana Saldías y Sebastián Shepherd Pérez.

---

## Funcionalidades

- **Inicio de sesión** con Firebase Authentication. En el primer ingreso, el
  usuario invitado crea su contraseña con su código de invitación.
- **Equipo** (solo gerente): ver a las personas de la organización y el estado
  de su acceso, invitar trabajadores (nombre, correo y RUT) y copiar o renovar
  su código. EasyLit no envía correos: el gerente copia un mensaje con el enlace
  y el código y se lo envía al trabajador.
- **Plantillas:** subir el Excel del mandante, marcar cada hoja como formulario o
  tabla, definir sus campos y editarlos o eliminarlos. Una plantilla ya usada no
  se puede borrar. Incluye una guía de ayuda paso a paso.
- **Transformar:** elegir mandante y plantilla, y subir la licitación (`.xlsx` o
  `.csv`, máximo 20 MB).
- **Revisión del mapeo:** resumen con el porcentaje de confianza, vista previa
  del documento, mover campos, elegir columnas de las tablas y el botón opcional
  «Limpiar con IA».
- **Generar y descargar** el Excel final con el formato del mandante.
- **Historial:** filtros por empresa, estado y fechas; ver, descargar o eliminar;
  tiempo de proceso y confianza promedio.

## Arquitectura

```
Navegador ──HTTPS──▶ easylit-web   (React + Vite, sitio estático en Render)
                          │
                          ▼ HTTPS / API REST
                     easylit-api    (Django + DRF con gunicorn, Render)
                     └─ worker Celery (corre en el mismo servicio, vía start.sh)
                          │
          ┌───────────────┼──────────────────┬──────────────────┐
          ▼               ▼                  ▼                  ▼
   easylit-db        easylit-redis     Cloudflare R2      API de Gemini
   (PostgreSQL)      (cola de tareas)  (archivos Excel)   (mapeo con IA)

   Firebase Authentication: el navegador inicia sesión y Django verifica el token.
```

| Componente | Dónde corre | Responsabilidad |
| --- | --- | --- |
| Frontend | Render · Static Site (`easylit-web`) | Pantallas de la aplicación |
| API | Render · Web Service (`easylit-api`) | Autenticación, plantillas, transformaciones, vista previa y generación del documento |
| Worker Celery | Mismo servicio que la API | Procesa cada archivo subido: limpieza, mapeo con Gemini y columnas de tablas |
| PostgreSQL | Render · PostgreSQL (`easylit-db`) | Datos de la aplicación |
| Redis | Render · Key Value (`easylit-redis`) | Cola que lleva los trabajos de la API al worker |
| Cloudflare R2 | Externo | Plantillas, licitaciones y documentos generados |
| Firebase Authentication | Externo (Google) | Credenciales de los usuarios |
| Gemini | Externo (Google) | Propone el mapeo y limpia textos cuando el usuario lo pide |

**Servicios publicados:**

- Aplicación: https://easylit-web.onrender.com
- API: https://easylit-api.onrender.com (estado: `/api/health/`)

El plan gratuito de Render apaga el servicio tras 15 minutos sin uso; el primer
acceso después de eso tarda cerca de un minuto.

## Tecnologías

| Capa | Tecnología |
| --- | --- |
| Frontend | React, TypeScript, Vite, React Query, CSS propio · Node 24 |
| Backend | Python 3.13, Django 5.2 LTS, Django REST Framework, Celery, pandas, openpyxl |
| Base de datos | PostgreSQL (producción), SQLite (desarrollo local) |
| Servicios | Render, Redis, Cloudflare R2, Firebase Authentication, API de Gemini |
| Calidad | Pruebas de Django, GitHub Actions (CI en cada push) |

## Estructura del repositorio

```
easylit-app/
├── render.yaml              servicios de Render
├── DESPLIEGUE.md            guía de despliegue paso a paso
├── .github/workflows/ci.yml integración continua
├── backend/
│   ├── build.sh, start.sh   scripts que usa Render
│   ├── requirements.txt
│   ├── .env.example         variables de entorno (sin valores reales)
│   ├── config/              settings (base, dev, prod), celery, urls
│   └── apps/
│       ├── common/          validación de archivos, utilidades
│       ├── organizaciones/  Organizacion
│       ├── usuarios/        Usuario, roles, Invitacion, login
│       ├── plantillas/      Plantilla, CampoPlantilla
│       └── transformaciones/ Transformacion, MapeoCampo, Bitacora,
│                            tareas del worker y servicios (limpieza, IA, generación)
└── frontend/
    ├── .env.example
    └── src/
        ├── app/             rutas
        ├── components/      layout y componentes comunes
        ├── features/        auth, plantillas, transformaciones, historial
        ├── lib/             utilidades (archivos, tiempos, Firebase)
        └── styles/          tokens.css y estilos globales
```

## Modelo de datos

Ocho tablas: `organizacion`, `usuario`, `invitacion`, `plantilla`,
`campo_plantilla`, `transformacion`, `mapeo_campo` y `bitacora`. Todas usan un
UUID como clave primaria. Las relaciones protegen la integridad: por ejemplo, no
se puede borrar una plantilla usada en una transformación, y un campo no puede
repetir su nombre dentro de la misma plantilla.

Estados de una transformación:

```
BORRADOR → LIMPIEZA → MAPEO_PROPUESTO → EN_REVISION → APROBADO → GENERADO
        cualquier paso puede terminar en ERROR (con el motivo en palabras simples)
```

## Roles

- **Superadmin:** administra el sistema y las organizaciones.
- **Gerente:** administra su organización e invita a sus trabajadores.
- **Trabajador:** crea plantillas y transformaciones, y ve las de su equipo.

Cada organización solo ve sus propios datos.

## Ejecutar en local

**Requisitos:** Python 3.13, Node 24 y Docker (para Redis).

**1. Backend** (PowerShell, carpeta `backend`):

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # completar los valores (ver más abajo)
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver    # http://localhost:8000
```

**2. Redis y worker** (otra terminal, carpeta `backend`, con `.venv` activo):

```powershell
docker run -d --name easylit-redis -p 6379:6379 redis:7   # la primera vez
docker start easylit-redis                                 # las siguientes
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"
celery -A config worker --loglevel=info --pool=solo
```

**3. Frontend** (otra terminal, carpeta `frontend`):

```powershell
npm ci
copy .env.example .env
npm run dev                   # http://localhost:5173
```

Con el superusuario, entrar a http://localhost:8000/admin para crear una
organización y su gerente. En local no se usan Firebase ni R2: el login es
propio (JWT) y los archivos quedan en `backend/media/`. Sin `GEMINI_API_KEY`, el
mapeo se propone solo por coincidencia de nombres.

### Variables de entorno

Las plantillas son `backend/.env.example` y `frontend/.env.example`. Los
archivos `.env` reales **nunca se suben al repositorio** (están en
`.gitignore`). En producción, los valores se cargan en el panel de Render.

| Variable | Para qué sirve |
| --- | --- |
| `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL` | Django, base de datos y cola |
| `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS` | Dominios permitidos |
| `GEMINI_API_KEY`, `IA_MODEL` | Conexión con Gemini |
| `R2_BUCKET`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Almacenamiento de archivos (producción) |
| `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENCIALES` | Verificación del login (producción) |
| `ARCHIVO_MAX_MB` | Peso máximo de los archivos (20 MB por defecto) |
| `VITE_API_URL`, `VITE_FIREBASE_*` | Configuración del frontend |

## Pruebas

```bash
cd backend
DJANGO_SETTINGS_MODULE=config.settings.dev .venv/Scripts/python.exe manage.py test apps.usuarios apps.transformaciones apps.plantillas
cd ../frontend
npx tsc --noEmit -p .
```

Las pruebas automáticas cubren, entre otras cosas:

- login correcto y fallido, y cierre de sesión;
- aislamiento de datos entre organizaciones;
- rechazo de archivos inválidos o de más de 20 MB;
- que los montos nunca se envíen a la IA;
- que la elección del usuario mande sobre la sugerencia de la IA;
- que una falla de Gemini no rompa el proceso;
- generación del documento, incluidas tablas y fórmulas.

GitHub Actions las ejecuta en cada push.

`test_modo_simulado_sin_clave` falla en un equipo que tenga una `GEMINI_API_KEY`
real en `.env`, porque esa prueba espera el modo sin clave. No es un error de la
aplicación.

## Seguridad

- Autenticación con Firebase; la API exige sesión en todas las rutas.
- Control de acceso por rol y por organización: nadie ve datos de otra empresa.
- Contraseñas con hash (PBKDF2). Ninguna clave ni contraseña está en el código.
- Validación de archivos por contenido real, no solo por extensión, y límite de
  peso.
- HTTPS en todos los servicios publicados.
- Los montos se reemplazan por `<número oculto>` antes de consultar a Gemini.
- Los errores se muestran en palabras simples, sin exponer detalles técnicos.

## Despliegue

Render crea los servicios a partir de `render.yaml`. Cada push a `main` vuelve a
desplegar la aplicación, y `build.sh` aplica las migraciones. La guía completa
está en [DESPLIEGUE.md](DESPLIEGUE.md).

## Usuario de prueba

Las credenciales de demostración se entregan directamente al docente evaluador.
No se publican en este repositorio.
