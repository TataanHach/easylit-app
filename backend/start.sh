#!/usr/bin/env bash
# Arranque del backend en Render: API (Gunicorn) y worker (Celery) en el MISMO
# servicio, para que la prueba quepa en el plan gratis. Los dos comparten las
# variables de entorno y los archivos van a Cloudflare R2, así que no necesitan
# disco compartido.
#
# Para separarlos más adelante (plan de pago): crear un servicio "worker" con
# `celery -A config worker --loglevel=info` y dejar aquí solo la línea de gunicorn.
set -o errexit

# Worker de Celery en segundo plano. --pool=solo: un solo proceso, para no pasar
# la memoria del plan gratis (cada proceso carga pandas).
celery -A config worker --loglevel=info --pool=solo &

# API. 1 proceso con hilos (misma razón: memoria). timeout alto: "Generar" procesa
# el Excel dentro de la petición.
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" \
  --workers 1 --threads 4 --timeout 120
