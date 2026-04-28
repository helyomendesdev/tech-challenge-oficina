from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ClienteViewSet,
    VeiculoViewSet,
    OrdemServicoViewSet,
    ItemPecaOSViewSet,  # Adicione este
    ServicoViewSet,
    PecaViewSet
)

router = DefaultRouter()
router.register(r'clientes', ClienteViewSet)
router.register(r'veiculos', VeiculoViewSet)
router.register(r'ordens-servico', OrdemServicoViewSet)
router.register(r'itens-pecas', ItemPecaOSViewSet)  # ESTA LINHA CRIA O POST QUE FALTA
router.register(r'servicos', ServicoViewSet)
router.register(r'pecas', PecaViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
