"""Rutas de plantillas, montadas bajo /api/."""
from rest_framework.routers import DefaultRouter

from .views import CampoPlantillaViewSet, PlantillaViewSet

router = DefaultRouter()
router.register(r"plantillas", PlantillaViewSet, basename="plantilla")
router.register(r"campos", CampoPlantillaViewSet, basename="campo")

urlpatterns = router.urls