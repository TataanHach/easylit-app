# Estructura del proyecto · EasyLit v2.8

Mapa del repositorio: qué hay en cada carpeta y en qué servicio de Render corre.
La visión general está en [README.md](README.md) y los pasos para desplegar, en
[DESPLIEGUE.md](DESPLIEGUE.md).

## Árbol del repositorio

```
easylit-app/
├── render.yaml                    servicios de Render (Blueprint)
├── README.md                      visión general, arquitectura, seguridad
├── DESPLIEGUE.md                  guía de despliegue paso a paso
├── ESTRUCTURA.md                  este archivo
├── CAMBIOS.md                     registro de versiones (qué cambió en cada una)
├── .github/workflows/ci.yml       pruebas y compilación en cada push a main
│
├── backend/                       Django + DRF + Celery → servicio easylit-api
│   ├── build.sh                   Render: instala, junta estáticos y aplica migraciones
│   ├── start.sh                   Render: arranca gunicorn y el worker Celery juntos
│   ├── requirements.txt
│   ├── .env.example               lista de variables de entorno (sin valores reales)
│   ├── config/
│   │   ├── settings/base.py       configuración común, límites de intentos, IA
│   │   ├── settings/prod.py       Render: PostgreSQL, R2, HTTPS/HSTS, CORS
│   │   ├── settings/dev.py        usada por las pruebas automáticas (CI)
│   │   ├── celery.py              configuración del worker
│   │   └── urls.py                /api/health/, /api/config/, /api/... y /admin/
│   └── apps/
│       ├── common/                validación de archivos, textos, health check
│       ├── organizaciones/        Organizacion (cada empresa cliente)
│       ├── usuarios/              Usuario, roles, Invitacion, login con Firebase
│       │   ├── api/limites.py     límites de intentos (respuesta 429)
│       │   ├── api/permissions.py permisos por rol
│       │   ├── firebase.py        verifica tokens y crea cuentas de invitados
│       │   ├── validadores.py     reglas de contraseña
│       │   ├── management/commands/vincular_firebase.py
│       │   └── tests.py
│       ├── plantillas/            Plantilla, CampoPlantilla
│       └── transformaciones/      Transformacion, MapeoCampo, Bitacora
│           ├── tasks.py           tarea Celery: limpieza + mapeo con IA
│           ├── services/
│           │   ├── limpieza.py       lectura y limpieza con pandas
│           │   ├── normalizacion.py  RUT, fechas, plazos, unidades, tildes
│           │   ├── ia.py             consulta a Gemini (montos ocultos)
│           │   ├── generacion.py     escribe la plantilla con openpyxl
│           │   └── errores.py        errores en palabras simples
│           └── tests.py, tests_worker.py, tests_normalizacion.py
│
└── frontend/                      React + TypeScript + Vite → servicio easylit-web
    ├── index.html
    ├── vite.config.ts
    ├── .env.example               variables VITE_* (sin valores reales)
    ├── public/                    íconos de la pestaña (isotipo)
    └── src/
        ├── main.tsx               punto de entrada (React Query, Router, burbuja de soporte)
        ├── api/client.ts          axios: token de sesión y renovación automática
        ├── app/router.tsx         rutas y rutas protegidas
        ├── assets/                logos
        ├── components/
        │   ├── layout/            menú lateral, barra superior y footer
        │   └── ui/                avisos, confirmaciones, burbuja de soporte
        ├── features/
        │   ├── auth/              login, crear contraseña, términos y condiciones
        │   ├── plantillas/        biblioteca, campos y ayudas
        │   ├── transformaciones/  transformar, revisar el mapeo, vista previa
        │   ├── historial/         tabla con filtros
        │   └── equipo/            invitar colaboradores (solo gerente)
        ├── lib/                   Firebase, RUT, errores, límites, soporte, versión
        ├── types/index.ts         tipos en espejo con la API
        └── styles/                tokens.css y estilos globales
```

## Servicios en Render

`render.yaml` crea cuatro servicios conectados entre sí. Además se usan tres
servicios externos.

| Servicio | Tipo | Qué corre | Carpeta |
|---|---|---|---|
| `easylit-web` | Static Site | React compilado | `frontend/` |
| `easylit-api` | Web Service | Django con gunicorn y el worker Celery (vía `start.sh`) | `backend/` |
| `easylit-db` | PostgreSQL | Base de datos | — |
| `easylit-redis` | Key Value | Cola de tareas de Celery | — |
| Cloudflare R2 | Externo | Plantillas, licitaciones y documentos generados | — |
| Firebase Authentication | Externo | Credenciales de los usuarios | — |
| Gemini | Externo | Propuesta de mapeo y limpieza de textos | — |

Cada push a `main` vuelve a desplegar lo que cambió, y `build.sh` aplica las
migraciones de la base. Las variables secretas se cargan en el panel de Render
(detalle en [DESPLIEGUE.md](DESPLIEGUE.md)).

## Dónde corre cada paso de una transformación

| Paso | Dónde corre | Código |
|---|---|---|
| Subir la licitación | `easylit-api` (guarda el archivo en R2) | `transformaciones/api/views.py` |
| Limpieza y mapeo con IA | Worker Celery, en el mismo servicio | `transformaciones/tasks.py`, `services/limpieza.py`, `services/ia.py` |
| Revisión y vista previa | `easylit-api` | `transformaciones/api/views.py` |
| Generar el documento | `easylit-api` (escribe en R2) | `services/generacion.py` |

## Integración continua

GitHub Actions ([ci.yml](.github/workflows/ci.yml)) corre en cada push y pull
request a `main`:

- **Backend:** revisa que no falten migraciones, ejecuta `manage.py check` y
  corre las 81 pruebas automáticas. Usa el modo simulado de la IA, así que no
  llama a Gemini ni a otros servicios externos.
- **Frontend:** revisa los tipos de TypeScript y compila la aplicación.
