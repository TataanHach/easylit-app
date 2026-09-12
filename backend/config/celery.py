"""
Configuración de Celery.

El worker procesa los archivos Excel fuera del ciclo HTTP: subir un itemizado de
200 filas y transformarlo puede tardar 30-60s, y eso no puede bloquear la
petición del usuario ni morir por timeout. Las tareas concretas se definen en el
bloque del worker.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("easylit")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
