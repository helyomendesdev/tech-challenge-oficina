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

class PoliciesDomainTest(TestCase):
    def test_policy_status_aceita_transicao_valida(self):
        OrdemServicoStatusPolicy.validar_transicao(
            StatusOrdemServico.RECEBIDA,
            StatusOrdemServico.DIAGNOSTICO,
        )

    def test_policy_status_rejeita_transicao_invalida(self):
        with self.assertRaises(TransicaoStatusInvalidaError):
            OrdemServicoStatusPolicy.validar_transicao(
                StatusOrdemServico.RECEBIDA,
                StatusOrdemServico.EXECUCAO,
            )

    def test_fila_define_status_visiveis_e_prioridade(self):
        self.assertTrue(
            FilaOrdemServicoPolicy.deve_aparecer_na_fila(
                StatusOrdemServico.EXECUCAO
            )
        )
        self.assertFalse(
            FilaOrdemServicoPolicy.deve_aparecer_na_fila(
                StatusOrdemServico.ENTREGUE
            )
        )
        self.assertLess(
            FilaOrdemServicoPolicy.prioridade(StatusOrdemServico.EXECUCAO),
            FilaOrdemServicoPolicy.prioridade(StatusOrdemServico.RECEBIDA),
        )

    def test_finalizacao_aceita_servicos_concluidos_e_pecas_utilizadas(self):
        FinalizacaoOrdemServicoPolicy.validar_finalizacao(
            StatusOrdemServico.EXECUCAO,
            [{"status": StatusItemServico.CONCLUIDO}],
            [{"quantidade": 2, "quantidade_utilizada": 2}],
        )

    def test_finalizacao_rejeita_servico_pendente(self):
        with self.assertRaises(RegraFinalizacaoOrdemServicoError):
            FinalizacaoOrdemServicoPolicy.validar_finalizacao(
                StatusOrdemServico.EXECUCAO,
                [{"status": StatusItemServico.PENDENTE}],
                [],
            )

    def test_finalizacao_rejeita_peca_nao_utilizada(self):
        with self.assertRaises(RegraFinalizacaoOrdemServicoError):
            FinalizacaoOrdemServicoPolicy.validar_finalizacao(
                StatusOrdemServico.EXECUCAO,
                [{"status": StatusItemServico.CONCLUIDO}],
                [{"quantidade": 2, "quantidade_utilizada": 1}],
            )
