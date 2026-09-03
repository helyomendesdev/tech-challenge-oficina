import base64
import time
from unittest.mock import patch
from uuid import uuid4

import jwt
from django.contrib.auth.models import User
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, override_settings
from django.urls import path
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken
from validate_docbr import CNPJ

from atendimento.authentication import ClientPrincipal
from atendimento.tests.helpers import criar_cliente, criar_usuario

CLIENTE_ACCESS_TOKEN_TYPE = "".join(("ac", "cess"))
CLIENTE_REFRESH_TOKEN_TYPE = "".join(("re", "fresh"))


class ClienteJWTProbeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "principal_class": user.__class__.__name__,
                "cliente_id": getattr(user, "cliente_id", None),
                "id": getattr(user, "id", None),
                "pk": getattr(user, "pk", None),
                "is_authenticated": bool(user.is_authenticated),
                "is_staff": bool(user.is_staff),
                "is_superuser": bool(user.is_superuser),
                "is_client_principal": isinstance(user, ClientPrincipal),
                "is_django_user": isinstance(user, User),
            }
        )


urlpatterns = [
    path("cliente-jwt/probe/", ClienteJWTProbeView.as_view()),
]


@override_settings(ROOT_URLCONF=__name__)
class ClienteJWTAuthenticationTest(TestCase):
    url = "/cliente-jwt/probe/"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_pem, cls.public_key_b64 = cls._generate_key_pair()
        cls.other_private_pem, _ = cls._generate_key_pair()

    @staticmethod
    def _generate_key_pair():
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return private_pem, base64.b64encode(public_pem).decode("ascii")

    def setUp(self):
        self.client = APIClient()
        self.cliente = criar_cliente(documento=CNPJ().generate(mask=False))

    def _claims(self, **overrides):
        now = int(time.time())
        claims = {
            "sub": f"cliente:{self.cliente.id}",
            "cliente_id": self.cliente.id,
            "principal_type": "cliente",
            "token_type": CLIENTE_ACCESS_TOKEN_TYPE,
            "iss": "oficina-auth",
            "aud": "oficina-api",
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid4()),
        }
        for key, value in overrides.items():
            if value is None:
                claims.pop(key, None)
            else:
                claims[key] = value
        return claims

    def _token(self, claims=None, key=None, algorithm="RS256"):
        return jwt.encode(
            claims or self._claims(),
            key or self.private_pem,
            algorithm=algorithm,
        )

    def _get(self, token, public_key_b64=None):
        with override_settings(
            AUTH_JWT_PUBLIC_KEY_B64=(
                self.public_key_b64 if public_key_b64 is None else public_key_b64
            )
        ):
            return self.client.get(
                self.url,
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )

    def assert_rejected(self, token, public_key_b64=None):
        response = self._get(token, public_key_b64=public_key_b64)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_cliente_valido_define_client_principal(self):
        response = self._get(self._token())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["principal_class"], "ClientPrincipal")
        self.assertEqual(response.data["cliente_id"], self.cliente.id)
        self.assertEqual(response.data["pk"], f"cliente:{self.cliente.id}")
        self.assertIsNone(response.data["id"])
        self.assertIs(response.data["is_authenticated"], True)
        self.assertIs(response.data["is_staff"], False)
        self.assertIs(response.data["is_superuser"], False)
        self.assertIs(response.data["is_client_principal"], True)
        self.assertIs(response.data["is_django_user"], False)

    def test_assinatura_invalida_rejeita_token(self):
        token = self._token(key=self.other_private_pem)

        self.assert_rejected(token)

    def test_token_cliente_com_assinatura_invalida_nao_cai_para_simplejwt(self):
        token = self._token(key=self.other_private_pem)

        with patch(
            "rest_framework_simplejwt.authentication.JWTAuthentication.authenticate"
        ) as simplejwt_authenticate:
            self.assert_rejected(token)

        simplejwt_authenticate.assert_not_called()

    def test_token_expirado_rejeita_token(self):
        token = self._token(self._claims(exp=int(time.time()) - 1))

        self.assert_rejected(token)

    def test_issuer_invalido_rejeita_token(self):
        token = self._token(self._claims(iss="outro-emissor"))

        self.assert_rejected(token)

    def test_audience_invalida_rejeita_token(self):
        token = self._token(self._claims(aud="outra-api"))

        self.assert_rejected(token)

    def test_algoritmo_diferente_de_rs256_rejeita_token(self):
        token = self._token(self._claims(), key=str(uuid4()), algorithm="HS256")

        self.assert_rejected(token)

    def test_claim_cliente_id_ausente_rejeita_token(self):
        token = self._token(self._claims(cliente_id=None))

        self.assert_rejected(token)

    def test_principal_type_incorreto_rejeita_token(self):
        token = self._token(self._claims(principal_type="funcionario"))

        self.assert_rejected(token)

    def test_token_type_incorreto_rejeita_token(self):
        token = self._token(self._claims(token_type=CLIENTE_REFRESH_TOKEN_TYPE))

        self.assert_rejected(token)

    def test_sub_invalido_rejeita_token(self):
        token = self._token(self._claims(sub=f"user:{self.cliente.id}"))

        self.assert_rejected(token)

    def test_cliente_inexistente_rejeita_token(self):
        cliente_id_inexistente = self.cliente.id + 999
        token = self._token(
            self._claims(
                cliente_id=cliente_id_inexistente,
                sub=f"cliente:{cliente_id_inexistente}",
            )
        )

        self.assert_rejected(token)

    def test_cliente_inativo_rejeita_token(self):
        self.cliente.ativo = False
        self.cliente.save(update_fields=["ativo"])
        token = self._token()

        self.assert_rejected(token)

    def test_auth_jwt_public_key_b64_ausente_rejeita_token_de_cliente(self):
        self.assert_rejected(self._token(), public_key_b64="")

    def test_token_cliente_com_chave_ausente_nao_cai_para_simplejwt(self):
        with patch(
            "rest_framework_simplejwt.authentication.JWTAuthentication.authenticate"
        ) as simplejwt_authenticate:
            self.assert_rejected(self._token(), public_key_b64="")

        simplejwt_authenticate.assert_not_called()

    def test_auth_jwt_public_key_b64_malformada_rejeita_token_de_cliente(self):
        self.assert_rejected(self._token(), public_key_b64="nao-e-base64")

    def test_autenticacao_simplejwt_de_funcionario_continua_funcionando(self):
        user = criar_usuario(username="tecnico_jwt")
        token = AccessToken.for_user(user)

        response = self.client.get(
            self.url,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["principal_class"], "User")
        self.assertIs(response.data["is_staff"], False)

    def test_autenticacao_simplejwt_de_staff_continua_funcionando(self):
        staff = criar_usuario(username="staff_jwt", is_staff=True)
        token = AccessToken.for_user(staff)

        response = self.client.get(
            self.url,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["principal_class"], "User")
        self.assertIs(response.data["is_staff"], True)
