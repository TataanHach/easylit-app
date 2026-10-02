# ─────────────────────────────────────────────────────────────
# Dockerfile del FRONTEND (React + Vite)
# Usa DOS etapas ("multi-stage"):
#   Etapa 1 (build): compila React a archivos estáticos.
#   Etapa 2 (serve): sirve esos archivos con un servidor web liviano (nginx).
# Así la caja final NO incluye Node ni las librerías de desarrollo: solo los
# archivos compilados y un servidor. Queda mucho más ligera.
# ─────────────────────────────────────────────────────────────

# ========== ETAPA 1: COMPILAR ==========
FROM node:20-slim AS build

WORKDIR /app

# Copiar primero los archivos de dependencias e instalarlas (aprovecha caché).
COPY package.json package-lock.json* ./
RUN npm install

# Copiar el resto del código y compilar.
COPY . .
RUN npm run build
# Esto genera la carpeta /app/dist con los archivos estáticos.

# ========== ETAPA 2: SERVIR ==========
FROM nginx:alpine

# Copiar los archivos compilados de la etapa anterior al servidor nginx.
COPY --from=build /app/dist /usr/share/nginx/html

# Copiar la configuración de nginx (para que las rutas de React funcionen).
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
