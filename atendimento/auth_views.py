"""
Views customizadas de autenticação JWT com logging de auditoria de segurança.

Estende as views padrão do simplejwt para registrar tentativas de login
(sucesso e falha) no logger de segurança.
"""
import logging
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from rest_framework_simplejwt.views import (
    TokenObtainPairView as BaseTokenObtainPairView,
    TokenRefreshView as BaseTokenRefreshView,
)

from atendimento.models import Cliente


logger_security = logging.getLogger('security')


class LoginCPFSerializer(serializers.Serializer):
    """Serializer para login por CPF do cliente."""
    cpf = serializers.CharField(max_length=14)


class LoginCPFView(APIView):
    """
    Autenticação por CPF do cliente.
    Retorna JWT se o cliente existe e está ativo.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginCPFSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cpf = serializer.validated_data['cpf']

        try:
            cliente = Cliente.objects.get(documento=cpf, ativo=True)
        except Cliente.DoesNotExist:
            logger_security.warning(
                "login_cpf_falha",
                extra={"cpf": cpf, "motivo": "nao_encontrado_ou_inativo"},
            )
            return Response(
                {"error": "não_autenticado"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Buscar ou criar usuário vinculado ao cliente
        user, _ = User.objects.get_or_create(
            username=cliente.documento,
            defaults={'email': cliente.email}
        )

        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        return Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "token_type": "Bearer",
            "expires_in": 900,
            "cliente_id": cliente.id,
        })


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
