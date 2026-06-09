from decimal import Decimal
from unittest import TestCase

from atendimento.domain.enums import StatusItemServico, StatusOrdemServico
from atendimento.domain.exceptions import (
    DocumentoInvalidoError,
    EstoqueInsuficienteError,
    PlacaInvalidaError,
    QuantidadeIndisponivelError,
    QuantidadeInvalidaError,
    RegraFinalizacaoOrdemServicoError,
    TransicaoStatusInvalidaError,
    ValorMonetarioInvalidoError,
)
from atendimento.domain.policies import (
    FilaOrdemServicoPolicy,
    FinalizacaoOrdemServicoPolicy,
    OrdemServicoStatusPolicy,
)
from atendimento.domain.services import (
    EstoqueDomainService,
    OrcamentoDomainService,
)
from atendimento.domain.value_objects import (
    Dinheiro,
    DocumentoCliente,
    PlacaVeiculo,
    Quantidade,
)

class ServicesDomainTest(TestCase):
    def test_orcamento_domain_service_calcula_total_conceitual(self):
        total = OrcamentoDomainService.calcular_total(
            servicos=[
                {"valor_mao_de_obra": "150.00"},
                {"valor_mao_de_obra": Decimal("50.00")},
            ],
            pecas=[
                {"valor_unitario": "35.50", "quantidade": 2},
                {"total_item": "10.00"},
            ],
        )

        self.assertIsInstance(total, Dinheiro)
        self.assertEqual(total.valor, Decimal("281.00"))

    def test_estoque_domain_service_aceita_disponibilidade_suficiente(self):
        EstoqueDomainService.validar_disponibilidade(
            estoque_atual=5,
            quantidade_solicitada=3,
            nome_peca="Filtro",
        )

    def test_estoque_domain_service_rejeita_estoque_insuficiente(self):
        with self.assertRaises(EstoqueInsuficienteError):
            EstoqueDomainService.validar_disponibilidade(
                estoque_atual=1,
                quantidade_solicitada=2,
                nome_peca="Filtro",
            )

    def test_estoque_domain_service_rejeita_consumo_acima_do_reservado(self):
        with self.assertRaises(QuantidadeIndisponivelError):
            EstoqueDomainService.validar_consumo_disponivel(
                quantidade_reservada=5,
                quantidade_utilizada=3,
                quantidade_solicitada=3,
                nome_peca="Filtro",
            )
