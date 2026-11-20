# EasyLit

**Tú defines el formato, EasyLit lo transforma para ti.**

Plataforma web que transforma el Excel de una licitación (formato propio de la
empresa) al formato que exige cada mandante, con un mapeo de columnas asistido
por IA y revisado por una persona.

> **La IA propone, una persona aprueba y el código determinista aplica.**

La IA solo sugiere qué columna del archivo de origen va a cada campo de la
plantilla. Los datos los lee y limpia **pandas** con reglas fijas y los escribe
**openpyxl** en la plantilla. Los montos y cantidades nunca se envían a la IA.

Versión **2.5 · Beta**, desplegada en **Render**.

Proyecto de Título — INACAP, Informática y Telecomunicaciones (TIHI84).
Equipo: Rocío Muñoz Pérez, Ernesto Quintana Saldías y Sebastián Shepherd Pérez.

---

## Acceso

- **Aplicación:** https://easylit-web.onrender.com
- **API:** https://easylit-api.onrender.com (estado: `/api/health/`)

El plan gratuito de Render apaga el servicio tras 15 minutos sin uso; el primer
acceso después de eso tarda cerca de un minuto.

Las credenciales de demostración se entregan directamente al docente evaluador.
No se publican en este repositorio.

## Funcionalidades

- **Inicio de sesión** con Firebase Authentication, en dos pasos: correo y luego
  contraseña.
- **Primer ingreso:** la persona invitada escribe su código de invitación, crea
  su contraseña y acepta los **términos y condiciones** (se pueden leer en una
  ventana antes de aceptar).
- **Equipo** (solo gerente): ver a las personas de la organización y el estado
  de su acceso, e **invitar colaboradores** (nombre, correo y RUT). EasyLit
  genera un código de 8 caracteres (ej. `K7M2-QX9P`) que el gerente ve **una sola
  vez** y envía al colaborador junto con el enlace de la aplicación. Si se
  pierde, se genera uno nuevo y el anterior deja de servir.
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
- **Soporte:** una burbuja «¿Necesitas soporte?» en todas las pantallas abre los
  canales de contacto (WhatsApp y correo) con un mensaje inicial ya escrito.
- **Footer** con los términos y condiciones, accesos a las secciones y el correo
  de contacto.

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

## Tecnologías

| Capa | Tecnología |
| --- | --- |
| Frontend | React, TypeScript, Vite, React Query, CSS propio · Node 24 |
| Backend | Python 3.13, Django 5.2 LTS, Django REST Framework, Celery, pandas, openpyxl |
| Base de datos | PostgreSQL |
| Servicios | Render, Redis, Cloudflare R2, Firebase Authentication, API de Gemini |
| Calidad | Pruebas automáticas de Django en GitHub Actions (en cada push) |

## Estructura del repositorio

```
easylit-app/
├── render.yaml              servicios de Render (Blueprint)
├── DESPLIEGUE.md            guía de despliegue paso a paso
├── .github/workflows/ci.yml integración continua
├── backend/
│   ├── build.sh, start.sh   scripts que usa Render (build y arranque)
│   ├── requirements.txt
│   ├── config/              settings, celery, urls
│   └── apps/
│       ├── common/          validación de archivos, utilidades
│       ├── organizaciones/  Organizacion
│       ├── usuarios/        Usuario, roles, Invitacion, login, límites de intentos
│       ├── plantillas/      Plantilla, CampoPlantilla
│       └── transformaciones/ Transformacion, MapeoCampo, Bitacora,
│                            tareas del worker y servicios (limpieza, IA, generación)
└── frontend/
    ├── public/              íconos de la pestaña (isotipo)
    └── src/
        ├── app/             rutas
        ├── assets/          logos
        ├── components/      layout, footer, burbuja de soporte y componentes comunes
        ├── features/        auth, equipo, plantillas, transformaciones, historial
        ├── lib/             utilidades (archivos, errores, soporte, Firebase)
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

- **Superadmin:** administra el sistema y las organizaciones (panel `/admin/`).
- **Gerente:** administra su organización e invita a sus colaboradores.
- **Trabajador:** crea plantillas y transformaciones, y ve las de su equipo.

Cada organización solo ve sus propios datos.

## Seguridad

- Autenticación con Firebase; la API exige sesión en todas las rutas.
- Control de acceso por rol y por organización: nadie ve datos de otra empresa.
- **Códigos de invitación** de 8 caracteres y un solo uso. En la base solo se
  guarda su huella (HMAC-SHA256), nunca el código, y no viajan dentro de enlaces.
- **Límites de intentos** en los accesos públicos (respuesta 429 con un aviso):

  | Acceso | Límite |
  | --- | --- |
  | Crear contraseña | 20 por hora, por IP |
  | Revisar correo (primer paso del login) | 30 por minuto, por IP |
  | Contraseña del login | Bloqueo propio de Firebase ante intentos repetidos |

- Contraseñas con hash (PBKDF2). Ninguna clave ni contraseña está en el código.
- Validación de archivos por contenido real, no solo por extensión, y límite de
  peso.
- HTTPS en todos los servicios publicados.
- Los montos se reemplazan por `<número oculto>` antes de consultar a Gemini.
- Datos tratados conforme a la Ley N° 19.628; el detalle está en los términos y
  condiciones de la aplicación.
- Los errores se muestran en palabras simples, sin exponer detalles técnicos.

## Pruebas

GitHub Actions ejecuta las pruebas automáticas en cada push. Cubren, entre otras
cosas:

- login correcto y fallido, y cierre de sesión;
- invitaciones: formato del código, que no quede legible en la base y que sirva
  una sola vez;
- límites de intentos en crear contraseña, revisar correo y login;
- aislamiento de datos entre organizaciones;
- rechazo de archivos inválidos o de más de 20 MB;
- que los montos nunca se envíen a la IA;
- que la elección del usuario mande sobre la sugerencia de la IA;
- que una falla de Gemini no rompa el proceso;
- generación del documento, incluidas tablas y fórmulas.

## Despliegue en Render

Render crea los servicios a partir de `render.yaml` (Blueprint). Cada push a
`main` vuelve a desplegar la aplicación, y `build.sh` aplica las migraciones de
la base de datos. La guía completa, incluida la creación del primer usuario,
está en [DESPLIEGUE.md](DESPLIEGUE.md).

### Variables de entorno (panel de Render)

Los valores se cargan en **Render → servicio → Environment**. Ninguno se guarda
en el repositorio.

**`easylit-api`**

| Variable | Para qué sirve |
| --- | --- |
| `SECRET_KEY` | Clave de Django (Render la genera sola) |
| `DATABASE_URL`, `REDIS_URL` | Base de datos y cola (Render las conecta solas) |
| `FRONTEND_URL` | URL de `easylit-web`, **sin `/` al final** (CORS) |
| `GEMINI_API_KEY`, `IA_MODEL` | Conexión con Gemini |
| `R2_BUCKET`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Almacenamiento de archivos |
| `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENCIALES` | Verificación del login (deben ser del mismo proyecto de Firebase) |
| `ARCHIVO_MAX_MB` | Peso máximo de los archivos (20 MB por defecto) |
| `LIMITE_*`, `NUM_PROXIES` | Opcionales: ajustar los límites de intentos |

**`easylit-web`** (se aplican al compilar: después de cambiarlas hay que volver
a desplegar el servicio)

| Variable | Para qué sirve |
| --- | --- |
| `VITE_API_URL` | URL de `easylit-api`, sin `/` al final y sin `/api` |
| `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID` | Login con Firebase |
| `VITE_SOPORTE_CORREO`, `VITE_SOPORTE_WHATSAPP` | Canales de la burbuja de soporte y del footer (WhatsApp con código de país, solo números) |

En Firebase → Authentication → **Dominios autorizados** debe estar la URL de
`easylit-web`; si no, el inicio de sesión se bloquea.
