# EasyLit · Frontend

React + TypeScript + Vite. Se despliega como Static Site en Render.

## Desarrollo local
```bash
npm install
npm run dev        # http://localhost:5173, con proxy /api → :8000
```
El backend debe estar corriendo en :8000 (`cd ../backend && python manage.py runserver`).

## Build de producción
```bash
npm run build      # genera dist/
```

## Estructura
```
src/
├── api/          cliente axios + JWT
├── app/          router y providers
├── components/   ui reutilizable + layout (sidebar, topbar)
├── features/     una carpeta por dominio (auth, transformaciones, ...)
├── hooks/        hooks compartidos
├── lib/          utilidades (formato RUT, montos, fechas)
├── types/        tipos en espejo con Django
└── styles/       tokens y estilos globales
```
