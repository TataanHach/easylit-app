# ─────────────────────────────────────────────────────────────
# Dockerfile del BACKEND (Django + Celery)
# Esta "receta" construye la caja que contiene el servidor.
# La misma imagen sirve para el backend (gunicorn) y el worker (celery);
# solo cambia el comando con que se arranca (eso va en docker-compose).
# ─────────────────────────────────────────────────────────────

# 1. Partimos de una imagen oficial de Python 3.12 "slim" (ligera).
FROM python:3.12-slim

# 2. Variables de entorno para que Python se comporte bien dentro de Docker:
#    - no genere archivos .pyc, y muestre los logs de inmediato.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. Dependencias del sistema que algunas librerías de Python necesitan
#    (pandas, psycopg). Se instalan y luego se limpia para no inflar la caja.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 4. Carpeta de trabajo dentro de la caja.
WORKDIR /app

# 5. Copiar PRIMERO solo el requirements.txt e instalar las librerías.
#    Se hace antes de copiar el código para aprovechar la caché de Docker:
#    si el código cambia pero las librerías no, no se reinstalan.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar el resto del código del backend.
COPY . .

# 7. El puerto por el que el backend escuchará.
EXPOSE 8000

# 8. Comando por defecto: arrancar con gunicorn (servidor de producción).
#    docker-compose puede sobreescribir esto para el worker.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
