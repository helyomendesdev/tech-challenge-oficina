from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from atendimento.application.dtos import (
    AbrirOrdemServicoInputDTO,
    ClienteInputDTO,
    PecaOrdemServicoInputDTO,
    VeiculoInputDTO,
)
from atendimento.application.use_cases.abrir_ordem_servico import (
    AbrirOrdemServicoUseCase,
)
from atendimento.domain.enums import StatusItemServico, StatusOrdemServico
from atendimento.infrastructure.repositories.django_cliente_repository import (
    DjangoClienteRepository,
)
from atendimento.infrastructure.repositories.django_ordem_servico_repository import (
    DjangoOrdemServicoRepository,
)
from atendimento.infrastructure.repositories.django_servico_repository import (
    DjangoServicoRepository,
)
from atendimento.infrastructure.repositories.django_veiculo_repository import (
    DjangoVeiculoRepository,
)
from atendimento.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)
from atendimento.models import (
    Cliente,
    ItemPecaOS,
    ItemServicoOS,
    OrdemServico,
    Peca,
    Servico,
    Veiculo,
)
from atendimento.tests.helpers import (
    api_client_for_user,
    create_cliente,
    create_item_peca_os,
    create_item_servico_os,
    create_ordem_servico,
    create_peca,
    create_staff_user,
    create_servico,
    create_superuser,
    create_user,
    create_veiculo,
)


class SpyNotificationAdapter:
    """Adapter de teste para verificar uso do NotificationPort."""

    def __init__(self):
        self.orcamentos = []

    def notificar_orcamento(self, ordem_servico_id, email, valor_total):
        self.orcamentos.append(
            {
                "ordem_servico_id": ordem_servico_id,
                "email": email,
                "valor_total": valor_total,
            }
        )
        return {"enviado": True}

    def notificar_conclusao(self, ordem_servico_id, email):
        return {"enviado": True}


class Phase2TestBase(TestCase):
    """Testes de integracao dos endpoints da Fase 2 da arquitetura limpa."""

    ABRIR_URL = "/api/v1/ordens-servico/abrir/"
    FILA_URL = "/api/v1/ordens-servico/fila/"
    ORCAMENTO_URL = "/api/v1/orcamentos/notificacoes/"
    STATUS_NOTIFICACOES_URL = "/api/v1/ordens-servico/status-notificacoes/"

    def setUp(self):
        self.usuario = create_user(username="tecnico")
        self.outro_usuario = create_user(username="outro-tecnico")
        self.staff = create_staff_user(username="gestor")
        self.superuser = create_superuser(username="admin")

    def api(self, usuario):
        return api_client_for_user(usuario)

    def status_url(self, ordem_servico):
        return f"/api/v1/ordens-servico/{ordem_servico.id}/status/"

    def criar_cliente(self, usuario=None, documento="52998224725", nome="Helio Teste"):
        return create_cliente(
            usuario=usuario,
            nome=nome,
            documento=documento,
            email=f"{documento}@example.com",
        )

    def criar_veiculo(self, cliente, usuario=None, placa="ABC1D23"):
        return create_veiculo(
            cliente=cliente,
            usuario=usuario,
            placa=placa,
            marca="Volkswagen",
            modelo="Golf",
            ano=2024,
        )

    def criar_servico(self, usuario=None, descricao="Troca de oleo", valor="150.00"):
        return create_servico(
            usuario=usuario,
            descricao=descricao,
            valor_mao_de_obra=Decimal(valor),
        )

    def criar_peca(self, usuario=None, nome="Filtro de oleo", valor="35.50", estoque=10):
        return create_peca(
            usuario=usuario,
            nome=nome,
            valor_unitario=Decimal(valor),
            estoque_atual=estoque,
        )

    def criar_os(
        self,
        usuario=None,
        status_os=StatusOrdemServico.RECEBIDA.value,
        documento="52998224725",
        placa="ABC1D23",
    ):
        cliente = self.criar_cliente(usuario=usuario, documento=documento)
        veiculo = self.criar_veiculo(cliente, usuario=usuario, placa=placa)
        return create_ordem_servico(
            cliente=cliente,
            veiculo=veiculo,
            usuario=usuario,
            status=status_os,
        )

    def definir_data_abertura(self, ordem_servico, data):
        OrdemServico.objects.filter(pk=ordem_servico.pk).update(data_abertura=data)
        ordem_servico.refresh_from_db()
        return ordem_servico

    def payload_abertura(
        self,
        servico,
        peca,
        documento="529.982.247-25",
        placa="abc1d23",
        quantidade=2,
    ):
        return {
            "cliente": {
                "nome": "Helio Teste",
                "documento": documento,
                "email": "helio@example.com",
                "telefone": "11999999999",
            },
            "veiculo": {
                "placa": placa,
                "marca": "Volkswagen",
                "modelo": "Golf",
                "ano": 2024,
            },
            "servicos": [servico.id],
            "pecas": [{"peca_id": peca.id, "quantidade": quantidade}],
        }
