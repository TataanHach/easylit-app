# Expone la app de Celery al importar el paquete config, para que el worker
# la descubra. La importación es tolerante: si Celery aún no está instalado
# (p. ej. al correr checks antes de `pip install`), no rompe manage.py.
try:
    from .celery import app as celery_app
    __all__ = ("celery_app",)
except ModuleNotFoundError:
    __all__ = ()
