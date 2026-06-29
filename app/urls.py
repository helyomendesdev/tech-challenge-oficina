from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from atendimento.auth_views import TokenObtainPairView, TokenRefreshView


def health_check(request):
    """Endpoint raiz para liveness/readiness probes do Kubernetes."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path('', health_check, name='health-check'),
    path('admin/', admin.site.urls),

    # Suas rotas da Oficina
    path('api/v1/', include('atendimento.urls')),

    # Rotas do JWT (A "Chave")
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Rotas do SWAGGER (O que estava faltando!)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
