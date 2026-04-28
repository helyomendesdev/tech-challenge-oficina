"""
Views customizadas de autenticação JWT com logging de auditoria de segurança.

Estende as views padrão do simplejwt para registrar tentativas de login
(sucesso e falha) no logger de segurança.
"""
import logging
from rest_framework_simplejwt.views import (
    TokenObtainPairView as BaseTokenObtainPairView,
    TokenRefreshView as BaseTokenRefreshView,
)

logger_security = logging.getLogger('security')


class TokenObtainPairView(BaseTokenObtainPairView):
    """
    View de login JWT com auditoria de segurança.

    Loga tentativas de autenticação (sucesso e falha) com IP e username.
    """

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        username = request.data.get('username', '<vazio>')
        ip = self._get_client_ip(request)

        if response.status_code == 200:
            logger_security.info(
                "login_success",
                extra={
                    "username": username,
                    "ip": ip,
                    "status_code": response.status_code,
                }
            )
        else:
            logger_security.warning(
                "login_failure",
                extra={
                    "username": username,
                    "ip": ip,
                    "status_code": response.status_code,
                }
            )

        return response

    def _get_client_ip(self, request):
        """Extrai o IP real do cliente, considerando proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '<desconhecido>')


class TokenRefreshView(BaseTokenRefreshView):
    """
    View de refresh de token JWT com auditoria.

    Loga tentativas de refresh (sucesso e falha).
    """

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        ip = self._get_client_ip(request)

        if response.status_code == 200:
            logger_security.info(
                "token_refresh_success",
                extra={"ip": ip, "status_code": response.status_code}
            )
        else:
            logger_security.warning(
                "token_refresh_failure",
                extra={"ip": ip, "status_code": response.status_code}
            )

        return response

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '<desconhecido>')
