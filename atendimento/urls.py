from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'clientes', views.ClienteViewSet)
router.register(r'veiculos', views.VeiculoViewSet)
router.register(r'ordens-servico', views.OrdemServicoViewSet)
router.register(r'itens-pecas', views.ItemPecaOSViewSet)
router.register(r'servicos', views.ServicoViewSet)
router.register(r'pecas', views.PecaViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path(
        'ordens-servico/<int:os_pk>/servicos/',
        views.ItemServicoOSViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='os-servicos-list',
    ),
    path(
        'ordens-servico/<int:os_pk>/servicos/<int:pk>/',
        views.ItemServicoOSViewSet.as_view({'get': 'retrieve', 'delete': 'destroy'}),
        name='os-servicos-detail',
    ),
    path(
        'ordens-servico/<int:os_pk>/servicos/<int:pk>/iniciar/',
        views.ItemServicoOSViewSet.as_view({'post': 'iniciar'}),
        name='os-servicos-iniciar',
    ),
    path(
        'ordens-servico/<int:os_pk>/servicos/<int:pk>/finalizar/',
        views.ItemServicoOSViewSet.as_view({'post': 'finalizar'}),
        name='os-servicos-finalizar',
    ),
]
