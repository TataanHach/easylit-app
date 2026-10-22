# EasyLit — notas para Claude

Transforma Excel de licitaciones (origen) al formato de una plantilla (destino).
Principio: **la IA propone, una persona aprueba, el código determinista aplica.**
Monorepo: `backend/` (Django + DRF + Celery) y `frontend/` (React + TS + Vite).

## Cómo trabajar con el usuario

- Todo en **español de Chile**, claro y sin jerga. El usuario no es experto en
  infraestructura: explica el porqué y da pasos concretos (dónde hacer clic, qué pegar).
- Mensajes para el usuario final (errores, avisos): en palabras simples, diciendo
  qué pasó y qué hacer. Comentarios del código, en español.
- Antes de cambiar algo grande o con costo (dependencias nuevas, servicios
  externos, Render), proponer y esperar el sí.
- No hacer commit ni push sin que lo pida.

## Reglas del producto

- **Privacidad:** montos y cantidades nunca se envían a Gemini (van como
  `<número oculto>`). `Organizacion.anonimizar_montos` está activo por defecto.
- **Prompts genéricos:** los prompts de `services/ia.py` no pueden tener pistas
  de una plantilla en particular (ej. "Numero = teléfono"). Solo reglas generales;
  el contexto (título, columnas, ejemplos) se manda como datos. Lo ambiguo lo
  decide el usuario con el selector de columnas.
- Prioridad al emparejar columnas de tablas: elección del usuario > mismo nombre
  o parecido > sugerencia de la IA (`generacion.parejas_columnas`).
- Si la plantilla trae una fórmula en una celda, se respeta. Las fórmulas del
  origen se copian solo si la tabla tiene la misma forma (`_formula_copiable`).

## Dónde corre cada cosa

- **Celery solo procesa al subir un archivo** (`procesar_transformacion`:
  limpieza, mapeo con Gemini, columnas con IA). **Generar el documento corre
  dentro de la API** (`generar` llama a `generar_documento_tarea` directo).
  → Cambios en el procesamiento: reiniciar el worker. Cambios en la generación o
  la vista previa: `runserver` los toma solo.
- Producción: **solo Render** (no hay Docker ni ngrok). `render.yaml` define
  `easylit-api` (gunicorn + Celery juntos, vía `backend/start.sh`),
  `easylit-web` (sitio estático), `easylit-redis` (Key Value) y `easylit-db`.
  Archivos en Cloudflare R2; login con Firebase. Guía: `DESPLIEGUE.md`.
  `start.sh` y `build.sh` los usa Render: no borrarlos.

## Desarrollo local (4 terminales)

```powershell
docker start easylit-redis                                  # 1. Redis
python manage.py runserver                                  # 2. backend (carpeta backend, .venv activo)
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"         # 3. worker
celery -A config worker --loglevel=info --pool=solo
npm run dev                                                 # 4. frontend → http://localhost:5173
```

En local no hay variables de Firebase: se usa el login propio (JWT).

## Tests

```bash
cd backend && DJANGO_SETTINGS_MODULE=config.settings.dev .venv/Scripts/python.exe manage.py test apps.transformaciones apps.plantillas
cd frontend && npx tsc --noEmit -p .
```

`test_modo_simulado_sin_clave` falla en local porque `.env` tiene una
`GEMINI_API_KEY` real (espera el modo sin clave). No es una regresión.

## Diagnosticar una transformación

- Base local: `backend/db.sqlite3`. Archivos en `backend/media/` (`origen/`,
  `plantillas/`, `generado/`). La última: `Transformacion.objects.order_by("-creada").first()`;
  mirar `resultado_limpieza` (`tablas_emparejadas`, `columnas_ia`,
  `columnas_usuario`) y `bitacora`.
- Regenerar en un archivo aparte (scratchpad), nunca sobre el generado del usuario.
- Para comprobar fórmulas, Excel está instalado: se puede abrir con COM desde
  PowerShell (`New-Object -ComObject Excel.Application`, solo lectura).
- Un documento "con celdas vacías" en fórmulas suele ser la **vista protegida**
  de Excel (no calcula hasta "Habilitar edición").

## Decisiones pendientes o descartadas

- Formatear teléfonos: **sacado**, no está en los planes por ahora.
- Historial en tiempo real: en veremos. Opción recomendada: Firestore como
  "timbre" (el backend avisa un cambio por organización y el frontend recarga).
- Selector "juntar columnas" (ej. Nombre + Apellido → Nombre completo): no existe.
