# EasyLit

Plataforma para transformar licitaciones de un formato Excel a otro, con mapeo
de columnas asistido por IA y verificación humana. El principio rector es:

> **La IA propone, un humano aprueba, el código determinista aplica.**

La IA nunca reescribe las filas del itemizado. Solo mira una muestra (encabezados
+ pocas filas) y propone a qué campo destino va cada columna origen. Una persona
revisa esa propuesta y recién entonces pandas aplica la transformación a todas las
filas, de forma reproducible y auditable.

## Arquitectura

```
GitHub (monorepo)
├── frontend/   React + TS + Vite   ─▶  Render · Static Site
└── backend/    Django + DRF        ─▶  Render · Web Service
                Celery worker       ─▶  Render · Background Worker
                PostgreSQL          ─▶  Render · PostgreSQL
                Redis               ─▶  Render · Key Value
```

## Roles

- **Superadmin** — EasyLit. Ve todo el sistema, gestiona organizaciones.
- **Gerente** — dueño de la cuenta de su organización. Da de alta a sus
  trabajadores registrando su correo; el trabajador crea su contraseña en el
  primer ingreso.
- **Trabajador** — crea y gestiona sus propias transformaciones; ve las del
  equipo según permisos.

Modelo de negocio **B** (una organización), con `Organizacion` presente desde el
día uno para migrar a **A** (multiempresa) sin reescritura.

## Estado del flujo de una transformación

```
BORRADOR → LIMPIEZA → MAPEO_PROPUESTO → EN_REVISION → APROBADO → GENERADO
                                          │
                                          └─▶ (rechazado) vuelve a MAPEO_PROPUESTO
   cualquier paso puede caer en → ERROR
```

## Estructura del backend

```
backend/
├── config/              # settings, urls, celery, wsgi/asgi
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── celery.py
│   └── urls.py
├── apps/
│   ├── organizaciones/  # Organizacion
│   ├── usuarios/        # Usuario, roles, invitación
│   ├── plantillas/      # Plantilla, CampoPlantilla, UnidadCanonica
│   └── transformaciones/# Transformacion, Partida, MapeoCampo, Bitacora
├── manage.py
├── requirements.txt
└── render.yaml (raíz del repo)
```

Este bloque entrega el modelo de datos. Los siguientes: auth, endpoints, worker,
frontend.
