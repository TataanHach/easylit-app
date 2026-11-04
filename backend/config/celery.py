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

# Si el worker muere a mitad de una tarea (en Render gratis: se queda sin memoria
# o el servicio se reinicia), la tarea vuelve a la cola en vez de perderse.
# - acks_late: la tarea se confirma al TERMINAR, no al recibirla.
# - visibility_timeout: tras 10 min sin confirmar, Redis la entrega de nuevo
#   (ninguna transformación debería tardar tanto).
# - prefetch 1: el worker no se reserva tareas que todavía no va a hacer.
app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 600},
    broker_connection_retry_on_startup=True,
)
app.autodiscover_tasks()
