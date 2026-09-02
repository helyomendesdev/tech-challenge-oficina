from django.contrib import admin
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.urls import path, include
from django.views.decorators.http import require_GET
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from atendimento.auth_views import TokenObtainPairView, TokenRefreshView, LoginCPFView


def health_check(request):
    """Endpoint raiz preservado por compatibilidade."""
    return JsonResponse({"status": "ok"})


@require_GET
def health_live(request):
    """Confirma que o processo da aplicacao esta respondendo."""
    return JsonResponse({"status": "ok"})


@require_GET
def health_ready(request):
    """Confirma que a aplicacao consegue consultar o banco de dados."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)

    return JsonResponse({"status": "ready"})


urlpatterns = [
    path('', health_check, name='health-check'),
    path('health/live/', health_live, name='health-live'),
    path('health/ready/', health_ready, name='health-ready'),
    path('admin/', admin.site.urls),

    # Suas rotas da Oficina
    path('api/v1/', include('atendimento.urls')),

    # Rotas do JWT (A "Chave")
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/cpf/', LoginCPFView.as_view(), name='token_cpf'),

    # Rotas do SWAGGER (O que estava faltando!)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
