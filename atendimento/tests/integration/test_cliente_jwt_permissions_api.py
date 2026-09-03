import base64
import json
import time
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from validate_docbr import CNPJ

from atendimento.models import OrdemServico, Veiculo
from atendimento.tests.helpers import (
    criar_cliente,
    criar_item_peca_os,
    criar_item_servico_os,
    criar_ordem_servico,
    criar_peca,
    criar_servico,
    criar_usuario,
    criar_veiculo,
)

CLIENTE_ACCESS_TOKEN_TYPE = "".join(("ac", "cess"))


class ClienteJWTPermissionsAPITest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_pem, cls.public_key_b64 = cls._generate_key_pair()

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
        self.api = APIClient()
        self.funcionario_a = criar_usuario(username="tecnico_cliente_jwt_a")
        self.funcionario_b = criar_usuario(username="tecnico_cliente_jwt_b")
        self.staff = criar_usuario(username="staff_cliente_jwt", is_staff=True)

        self.cliente_a = criar_cliente(
            usuario=self.funcionario_a,
            nome="Cliente Integracao A",
            documento=CNPJ().generate(mask=False),
            email="cliente-a@example.com",
        )
        self.cliente_b = criar_cliente(
            usuario=self.funcionario_b,
            nome="Cliente Integracao B",
            documento=CNPJ().generate(mask=False),
            email="cliente-b@example.com",
        )
        self.veiculo_a = criar_veiculo(
            self.cliente_a,
            usuario=self.funcionario_a,
            placa="JWA1A01",
            marca="Fiat",
            modelo="Cronos",
        )
        self.veiculo_b = criar_veiculo(
            self.cliente_b,
            usuario=self.funcionario_b,
            placa="JWB1B02",
            marca="Toyota",
            modelo="Corolla",
        )
        self.os_a = criar_ordem_servico(
            self.cliente_a,
            self.veiculo_a,
            usuario=self.funcionario_a,
        )
        self.os_b = criar_ordem_servico(
            self.cliente_b,
            self.veiculo_b,
            usuario=self.funcionario_b,
        )
        self.servico_a = criar_servico(
            usuario=self.funcionario_a,
            descricao="Alinhamento Cliente A",
        )
        self.peca_a = criar_peca(
            usuario=self.funcionario_a,
            nome="Filtro Cliente A",
            estoque_atual=5,
        )
        criar_item_servico_os(self.os_a, self.servico_a, self.funcionario_a)
        criar_item_peca_os(
            self.os_a,
            self.peca_a,
            usuario=self.funcionario_a,
            quantidade=1,
        )

    def _claims(self, cliente_id):
        now = int(time.time())
        return {
            "sub": f"cliente:{cliente_id}",
            "cliente_id": cliente_id,
            "principal_type": "cliente",
            "token_type": CLIENTE_ACCESS_TOKEN_TYPE,
            "iss": "oficina-auth",
            "aud": "oficina-api",
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid4()),
        }

    def _token_cliente(self, cliente):
        return jwt.encode(
            self._claims(cliente.id),
            self.private_pem,
            algorithm="RS256",
        )

    def _request_cliente(self, method, path, cliente=None, data=None):
        token = self._token_cliente(cliente or self.cliente_a)
        request = getattr(self.api, method)
        with override_settings(AUTH_JWT_PUBLIC_KEY_B64=self.public_key_b64):
            return request(
                path,
                data or {},
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )

    def _ids(self, response):
        return [item["id"] for item in response.data["results"]]

    def _assert_sem_dados_sensiveis(self, value):
        if isinstance(value, dict):
            for key, item in value.items():
                self.assertNotIn(key, {"created_by", "documento", "token", "segredo"})
                self._assert_sem_dados_sensiveis(item)
        elif isinstance(value, list):
            for item in value:
                self._assert_sem_dados_sensiveis(item)

    def test_cliente_lista_somente_os_proprios_veiculos(self):
        response = self._request_cliente("get", "/api/v1/veiculos/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(response), [self.veiculo_a.id])

    def test_cliente_acessa_veiculo_proprio(self):
        response = self._request_cliente(
            "get", f"/api/v1/veiculos/{self.veiculo_a.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.veiculo_a.id)
        self.assertNotIn("created_by", response.data)
        self.assertNotIn("cliente", response.data)

    def test_cliente_recebe_404_ao_acessar_veiculo_de_outro_cliente(self):
        response = self._request_cliente(
            "get", f"/api/v1/veiculos/{self.veiculo_b.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cliente_lista_somente_as_proprias_os(self):
        response = self._request_cliente("get", "/api/v1/ordens-servico/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(response), [self.os_a.id])

    def test_cliente_acessa_os_propria_sem_campos_internos(self):
        response = self._request_cliente(
            "get",
            f"/api/v1/ordens-servico/{self.os_a.id}/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.os_a.id)
        self.assertNotIn("created_by", response.data)
        self.assertNotIn("cliente", response.data)
        self.assertIn("veiculo", response.data)

    def test_cliente_recebe_404_ao_acessar_os_de_outro_cliente(self):
        response = self._request_cliente(
            "get",
            f"/api/v1/ordens-servico/{self.os_b.id}/",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cliente_consulta_status_da_propria_os(self):
        response = self._request_cliente(
            "get",
            f"/api/v1/ordens-servico/{self.os_a.id}/status/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ordem_servico_id"], self.os_a.id)
        self.assertEqual(response.data["status"], self.os_a.status)

    def test_cliente_recebe_404_ao_consultar_status_de_os_de_outro_cliente(self):
        response = self._request_cliente(
            "get",
            f"/api/v1/ordens-servico/{self.os_b.id}/status/",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_consulta_cliente_sem_autenticacao_retorna_401(self):
        response = APIClient().get("/api/v1/ordens-servico/consulta-cliente/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cliente_usa_consulta_cliente_e_recebe_somente_suas_informacoes(self):
        response = self._request_cliente(
            "get",
            "/api/v1/ordens-servico/consulta-cliente/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(response), [self.os_a.id])

    def test_documento_de_outro_cliente_nao_amplia_escopo_do_cliente_jwt(self):
        response = self._request_cliente(
            "get",
            "/api/v1/ordens-servico/consulta-cliente/",
            data={"identificador": self.cliente_b.documento},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(response), [self.os_a.id])

    def test_cliente_jwt_recebe_403_em_writes(self):
        writes = [
            ("post", "/api/v1/veiculos/", {"cliente": self.cliente_a.id}),
            ("patch", f"/api/v1/veiculos/{self.veiculo_a.id}/", {"modelo": "Argo"}),
            ("delete", f"/api/v1/veiculos/{self.veiculo_a.id}/", {}),
            ("post", "/api/v1/ordens-servico/", {"cliente": self.cliente_a.id}),
            (
                "patch",
                f"/api/v1/ordens-servico/{self.os_a.id}/",
                {"veiculo": self.veiculo_a.id},
            ),
            ("delete", f"/api/v1/ordens-servico/{self.os_a.id}/", {}),
            ("post", "/api/v1/clientes/", {"nome": "Novo Cliente"}),
            ("patch", f"/api/v1/clientes/{self.cliente_a.id}/", {"nome": "Outro"}),
            ("post", "/api/v1/ordens-servico/abrir/", {}),
            ("post", f"/api/v1/ordens-servico/{self.os_a.id}/iniciar-diagnostico/", {}),
        ]

        for method, path, data in writes:
            with self.subTest(method=method, path=path):
                response = self._request_cliente(method, path, data=data)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cliente_jwt_nao_acessa_endpoints_admin_ou_get_nao_autorizado(self):
        urls = [
            "/api/v1/clientes/",
            "/api/v1/servicos/",
            "/api/v1/pecas/",
            "/api/v1/itens-pecas/",
            "/api/v1/ordens-servico/fila/",
            f"/api/v1/ordens-servico/{self.os_a.id}/metricas/",
            "/api/v1/ordens-servico/metricas/tempo-medio/",
            f"/api/v1/ordens-servico/{self.os_a.id}/servicos/",
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self._request_cliente("get", url)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_created_by_nunca_recebe_client_principal(self):
        total_veiculos = Veiculo.objects.count()
        total_ordens = OrdemServico.objects.count()

        response = self._request_cliente(
            "post",
            "/api/v1/veiculos/",
            data={
                "cliente": self.cliente_a.id,
                "placa": "JWX1C03",
                "marca": "VW",
                "modelo": "Polo",
                "ano": 2025,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Veiculo.objects.count(), total_veiculos)
        self.assertEqual(OrdemServico.objects.count(), total_ordens)

    def test_funcionario_continua_vendo_e_alterando_seus_recursos(self):
        token = AccessToken.for_user(self.funcionario_a)

        response = self.api.patch(
            f"/api/v1/veiculos/{self.veiculo_a.id}/",
            {"modelo": "Cronos Precision"},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        list_response = self.api.get(
            "/api/v1/veiculos/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["modelo"], "Cronos Precision")
        self.assertEqual(self._ids(list_response), [self.veiculo_a.id])

    def test_staff_continua_acessando_todos_os_recursos(self):
        token = AccessToken.for_user(self.staff)

        response = self.api.get(
            "/api/v1/veiculos/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(self._ids(response)), {self.veiculo_a.id, self.veiculo_b.id}
        )

    def test_simplejwt_de_funcionario_continua_funcionando(self):
        token = AccessToken.for_user(self.funcionario_a)

        response = self.api.get(
            f"/api/v1/ordens-servico/{self.os_a.id}/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.os_a.id)

    def test_endpoints_publicos_restantes_continuam_funcionando(self):
        anonimo = APIClient()

        health = anonimo.get("/health/live/")
        schema = anonimo.get("/api/schema/")

        self.assertEqual(health.status_code, status.HTTP_200_OK)
        self.assertEqual(schema.status_code, status.HTTP_200_OK)

    def test_openapi_documenta_bearer_de_cliente_jwt(self):
        response = APIClient().get(
            "/api/schema/",
            HTTP_ACCEPT="application/json",
        )
        schema = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        security_schemes = schema["components"]["securitySchemes"]
        self.assertEqual(security_schemes["ClienteJWTBearerAuth"]["type"], "http")
        self.assertEqual(
            security_schemes["ClienteJWTBearerAuth"]["bearerFormat"],
            "Cliente JWT RS256",
        )

    def test_respostas_cliente_nao_expoem_dados_sensiveis_ou_de_outro_cliente(self):
        responses = {
            "veiculos": self._request_cliente("get", "/api/v1/veiculos/"),
            "ordens": self._request_cliente("get", "/api/v1/ordens-servico/"),
            "consulta": self._request_cliente(
                "get",
                "/api/v1/ordens-servico/consulta-cliente/",
            ),
        }

        for response in responses.values():
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self._assert_sem_dados_sensiveis(response.data)
            self.assertNotIn(self.veiculo_b.placa, str(response.data))

        self.assertEqual(self._ids(responses["veiculos"]), [self.veiculo_a.id])
        self.assertEqual(self._ids(responses["ordens"]), [self.os_a.id])
        self.assertEqual(self._ids(responses["consulta"]), [self.os_a.id])
