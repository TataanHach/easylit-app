"""Rutas de plantillas, montadas bajo /api/."""
from rest_framework.routers import DefaultRouter

from .views import CampoPlantillaViewSet, PlantillaViewSet, UnidadCanonicaViewSet

router = DefaultRouter()
router.register(r"plantillas", PlantillaViewSet, basename="plantilla")
router.register(r"campos", CampoPlantillaViewSet, basename="campo")
router.register(r"unidades", UnidadCanonicaViewSet, basename="unidad")

urlpatterns = router.urls