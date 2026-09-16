# Mostrar tu app con ngrok (guía paso a paso)

Objetivo: obtener una URL pública (https://algo.ngrok.app) que apunta a tu PC,
para que otra persona vea tu app. Mientras tu PC y las terminales estén
corriendo, la URL funciona. Al cerrar, deja de funcionar.

═══════════════════════════════════════════════════════════
PASO 1 — INSTALAR NGROK
═══════════════════════════════════════════════════════════

1. Ve a https://ngrok.com y crea una cuenta gratis (o entra con Google/GitHub).
2. Descarga ngrok para Windows desde https://ngrok.com/download
3. Descomprime el archivo. Te queda un "ngrok.exe".
4. En el panel de ngrok, copia tu "authtoken" (una clave larga).
   Está en: dashboard.ngrok.com -> "Your Authtoken".
5. Abre PowerShell donde está ngrok.exe y corre (con tu token):

     .\ngrok config add-authtoken TU_TOKEN_AQUI

   Esto solo se hace una vez.

═══════════════════════════════════════════════════════════
PASO 2 — AJUSTAR VITE PARA QUE ACEPTE NGROK
═══════════════════════════════════════════════════════════

Vite, por seguridad, bloquea dominios desconocidos. Hay que decirle que
acepte ngrok. Reemplaza tu archivo:

  frontend/vite.config.ts   ->  usa el que viene en esta carpeta

(Le añadí "allowedHosts" para que acepte los dominios de ngrok.)

═══════════════════════════════════════════════════════════
PASO 3 — ARRANCAR TODO (4 terminales)
═══════════════════════════════════════════════════════════

Necesitas estas 4 cosas corriendo a la vez:

Terminal 1 — Redis (Docker):
   docker start easylit-redis
   (o el comando docker run si es la primera vez)

Terminal 2 — Backend (en carpeta backend, con .venv activo):
   python manage.py runserver

Terminal 3 — Worker (en carpeta backend, con .venv activo):
   $env:DJANGO_SETTINGS_MODULE = "config.settings.dev"
   celery -A config worker --loglevel=info --pool=solo

Terminal 4 — Frontend (en carpeta frontend):
   npm run dev

═══════════════════════════════════════════════════════════
PASO 4 — ABRIR EL TÚNEL
═══════════════════════════════════════════════════════════

En una QUINTA terminal (donde está ngrok.exe):

   .\ngrok http 5173

ngrok te mostrará una línea como:
   Forwarding   https://abcd-1234.ngrok-free.app -> http://localhost:5173

Esa URL "https://abcd-1234.ngrok-free.app" es la que compartes. Cualquiera
que la abra verá tu app, funcionando con tu login, tu backend, tu Gemini.

═══════════════════════════════════════════════════════════
NOTAS
═══════════════════════════════════════════════════════════

- La URL cambia cada vez que abres ngrok (en el plan gratuito). Si quieres una
  fija, ngrok lo ofrece en su plan de pago.

- Mientras tu PC esté encendido y las 5 terminales corriendo, la app funciona
  para quien tenga la URL. Al cerrar cualquiera, deja de andar.

- La primera vez que alguien abra la URL de ngrok gratis, verá una pantalla de
  advertencia de ngrok con un botón "Visit Site". Es normal; le da clic y entra.

- Como es tu PC, la persona usa TUS datos (tu base de datos local, tu clave de
  Gemini). Perfecto para mostrar; no para que muchos lo usen en serio.
