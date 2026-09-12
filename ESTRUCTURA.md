# Estructura del proyecto y despliegue

Este documento explica **dónde va cada cosa** y **cómo se despliega**. Es el mapa
del monorepo.

## Árbol completo

```
easylit-app/                      ← raíz del repositorio en GitHub
│
├── render.yaml                   ← define los 5 servicios de Render
├── .gitignore
├── README.md                     ← visión general y modelo de datos
├── ESTRUCTURA.md                 ← este archivo
│
├── .github/workflows/ci.yml      ← compila back y front en cada push
│
├── backend/                      ← Django (Web Service + Worker en Render)
│   ├── build.sh                  ← script que Render ejecuta al desplegar
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example              ← plantilla de variables (copiar a .env)
│   │
│   ├── config/                   ← configuración del proyecto
│   │   ├── settings/
│   │   │   ├── base.py           ← común a todos los entornos
│   │   │   ├── dev.py            ← desarrollo local (SQLite, DEBUG)
│   │   │   └── prod.py           ← Render (Postgres, seguridad, CORS)
│   │   ├── celery.py             ← configuración del worker
│   │   ├── urls.py               ← rutas raíz (health + API)
│   │   ├── wsgi.py / asgi.py
│   │   └── __init__.py
│   │
│   └── apps/                     ← una app por dominio
│       ├── common/               ← health check y utilidades transversales
│       ├── organizaciones/       ← Organizacion
│       ├── usuarios/             ← Usuario, roles, Invitacion
│       │   └── api/              ← serializers, views, urls (bloque 2)
│       ├── plantillas/           ← Plantilla, CampoPlantilla, UnidadCanonica
│       │   └── api/              ← (bloque 3)
│       └── transformaciones/     ← Transformacion, Partida, MapeoCampo, Bitacora
│           ├── api/              ← (bloque 3)
│           └── services/         ← limpieza, IA, validación (bloque 4)
│
└── frontend/                     ← React (Static Site en Render)
    ├── package.json
    ├── vite.config.ts            ← proxy /api → :8000 en dev
    ├── tsconfig.json
    ├── index.html                ← raíz de Vite
    ├── .env.example
    │
    └── src/
        ├── main.tsx              ← punto de entrada (React Query + Router)
        ├── api/
        │   └── client.ts         ← axios con JWT y refresco automático
        ├── app/
        │   └── router.tsx        ← mapa de rutas
        ├── components/
        │   ├── ui/               ← botones, inputs, badges (bloque frontend)
        │   └── layout/           ← sidebar, topbar (bloque frontend)
        ├── features/             ← una carpeta por dominio de pantalla
        │   ├── auth/             ← login, registro, crear contraseña
        │   ├── transformaciones/ ← wizard: cargar, limpiar, mapear, generar
        │   ├── plantillas/       ← biblioteca de formatos
        │   ├── historial/        ← tabla con filtros por alcance
        │   └── equipo/           ← gestión de usuarios (gerente)
        ├── hooks/                ← hooks compartidos
        ├── lib/                  ← formato de RUT, montos, fechas
        ├── types/
        │   └── index.ts          ← tipos en espejo con Django
        └── styles/
            ├── tokens.css        ← paleta y escala (del prototipo)
            └── global.css
```

## Cómo se despliega en Render

Al conectar el repositorio a Render y apuntar al `render.yaml`, se crean cinco
servicios cableados entre sí automáticamente:

| Servicio | Tipo Render | Qué corre | Carpeta |
|---|---|---|---|
| easylit-web | Static Site | React compilado | `frontend/` |
| easylit-api | Web Service | Django + Gunicorn | `backend/` |
| easylit-worker | Background Worker | Celery | `backend/` |
| easylit-db | PostgreSQL | Base de datos | — |
| easylit-redis | Key Value | Cola de Celery | — |

Cada push a `main` redespliega lo que cambió. Las variables secretas
(`GEMINI_API_KEY`, `ALLOWED_HOSTS`, `FRONTEND_URL`, `VITE_API_URL`) se pegan una
vez en el panel de Render; las demás se generan o cablean solas.

## Cómo correrlo en tu máquina

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # ajusta si quieres
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver    # http://localhost:8000
```

**Frontend** (en otra terminal):
```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

El proxy de Vite reenvía `/api` al Django local, así que no hay problemas de CORS
en desarrollo.

## Qué falta (próximos bloques)

Este esqueleto tiene el modelo de datos, la infraestructura y el cableado
completos y verificados. Falta llenar la lógica:

2. **Autenticación** — endpoints JWT, invitación del gerente, primer ingreso.
3. **Endpoints REST** — subir, listar, mapear, aprobar, generar.
4. **Worker** — limpieza con pandas, propuesta con Gemini, validación aritmética.
5. **Frontend** — las pantallas React conectadas a la API.
```
