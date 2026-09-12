"""Rutas de transformaciones, montadas bajo /api/."""
from rest_framework.routers import DefaultRouter

from .views import TransformacionViewSet

router = DefaultRouter()
router.register(r"transformaciones", TransformacionViewSet, basename="transformacion")

urlpatterns = router.urls
