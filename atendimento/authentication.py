import base64
import binascii
from dataclasses import dataclass
from uuid import UUID

import jwt
from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header

from atendimento.models import Cliente

CLIENTE_JWT_AUDIENCE = "oficina-api"
CLIENTE_JWT_ISSUER = "oficina-auth"
CLIENTE_JWT_ALGORITHM = "RS256"
CLIENTE_JWT_REQUIRED_CLAIMS = {
    "sub",
    "cliente_id",
    "principal_type",
    "token_type",
    "iss",
    "aud",
    "iat",
    "exp",
    "jti",
}


@dataclass(frozen=True)
class ClientPrincipal:
    cliente_id: int
    cliente: Cliente

    is_authenticated = True
    is_staff = False
    is_superuser = False
    id = None

    @property
    def pk(self):
        return f"cliente:{self.cliente_id}"


class ClienteJWTAuthentication(BaseAuthentication):
    """Autentica JWT externo de Cliente sem representar o cliente como User."""

    www_authenticate_realm = "api"

    def authenticate(self, request):
        raw_token = self._get_bearer_token(request)
        if raw_token is None or not self._looks_like_cliente_jwt(raw_token):
            return None

        claims = self._decode_and_validate(raw_token)
        cliente_id = self._validate_claims(claims)
        cliente = self._get_cliente_ativo(cliente_id)
        return ClientPrincipal(cliente_id=cliente.id, cliente=cliente), claims

    def authenticate_header(self, request):
        return f'Bearer realm="{self.www_authenticate_realm}"'

    def _get_bearer_token(self, request):
        header = get_authorization_header(request).split()
        if not header:
            return None
        if header[0].lower() != b"bearer" or len(header) != 2:
            return None
        try:
            return header[1].decode("utf-8")
        except UnicodeDecodeError:
            return None

    def _looks_like_cliente_jwt(self, raw_token):
        try:
            claims = jwt.decode(
                raw_token,
                options={"verify_signature": False, "verify_aud": False},
            )
        except jwt.InvalidTokenError:
            return False

        sub = claims.get("sub")
        return (
            claims.get("principal_type") == "cliente"
            or (isinstance(sub, str) and sub.startswith("cliente:"))
            or (claims.get("aud") == CLIENTE_JWT_AUDIENCE and "cliente_id" in claims)
        )

    def _decode_and_validate(self, raw_token):
        public_key = self._public_key()
        try:
            return jwt.decode(
                raw_token,
                public_key,
                algorithms=[CLIENTE_JWT_ALGORITHM],
                issuer=CLIENTE_JWT_ISSUER,
                audience=CLIENTE_JWT_AUDIENCE,
                options={"require": sorted(CLIENTE_JWT_REQUIRED_CLAIMS)},
            )
        except jwt.ExpiredSignatureError as exc:
            raise exceptions.AuthenticationFailed("Token de cliente expirado.") from exc
        except jwt.InvalidTokenError as exc:
            raise exceptions.AuthenticationFailed("Token de cliente invalido.") from exc

    def _public_key(self):
        encoded_key = getattr(settings, "AUTH_JWT_PUBLIC_KEY_B64", "")
        if not encoded_key:
            raise exceptions.AuthenticationFailed(
                "Chave publica de cliente JWT nao configurada."
            )
        try:
            return base64.b64decode(encoded_key, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise exceptions.AuthenticationFailed(
                "Chave publica de cliente JWT invalida."
            ) from exc

    def _validate_claims(self, claims):
        cliente_id = claims.get("cliente_id")
        if isinstance(cliente_id, bool) or not isinstance(cliente_id, int):
            raise exceptions.AuthenticationFailed("Claim cliente_id deve ser inteiro.")
        if cliente_id <= 0:
            raise exceptions.AuthenticationFailed("Claim cliente_id invalida.")
        if claims.get("principal_type") != "cliente":
            raise exceptions.AuthenticationFailed("principal_type invalido.")
        if claims.get("token_type") != "access":
            raise exceptions.AuthenticationFailed("token_type invalido.")
        if claims.get("sub") != f"cliente:{cliente_id}":
            raise exceptions.AuthenticationFailed("sub invalido.")
        try:
            UUID(str(claims.get("jti")))
        except (TypeError, ValueError) as exc:
            raise exceptions.AuthenticationFailed("jti invalido.") from exc
        return cliente_id

    def _get_cliente_ativo(self, cliente_id):
        cliente = Cliente.objects.filter(pk=cliente_id).first()
        if cliente is None:
            raise exceptions.AuthenticationFailed("Cliente nao encontrado.")
        if not cliente.ativo:
            raise exceptions.AuthenticationFailed("Cliente inativo.")
        return cliente
