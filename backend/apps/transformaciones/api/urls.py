"""Rutas de transformaciones, montadas bajo /api/."""
from rest_framework.routers import DefaultRouter

from .views import MapeoCampoViewSet, TransformacionViewSet

router = DefaultRouter()
router.register(r"transformaciones", TransformacionViewSet, basename="transformacion")
router.register(r"mapeos", MapeoCampoViewSet, basename="mapeo")

urlpatterns = router.urls