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

class ValueObjectsDomainTest(TestCase):
    def test_documento_cliente_normaliza_cpf_valido(self):
        documento = DocumentoCliente("529.982.247-25")

        self.assertEqual(documento.valor, "52998224725")
        self.assertEqual(str(documento), "52998224725")

    def test_documento_cliente_rejeita_documento_invalido(self):
        with self.assertRaises(DocumentoInvalidoError):
            DocumentoCliente("111.111.111-11")

    def test_placa_veiculo_normaliza_mercosul(self):
        placa = PlacaVeiculo("abc1d23")

        self.assertEqual(placa.valor, "ABC1D23")

    def test_placa_veiculo_rejeita_formato_invalido(self):
        with self.assertRaises(PlacaInvalidaError):
            PlacaVeiculo("ABC123")

    def test_quantidade_aceita_inteiro_positivo(self):
        quantidade = Quantidade("3")

        self.assertEqual(quantidade.valor, 3)
        self.assertEqual(int(quantidade), 3)

    def test_quantidade_rejeita_zero_decimal_e_booleano(self):
        for valor in (0, "1.5", True):
            with self.subTest(valor=valor):
                with self.assertRaises(QuantidadeInvalidaError):
                    Quantidade(valor)

    def test_dinheiro_aceita_decimal_nao_negativo(self):
        dinheiro = Dinheiro("10.50")

        self.assertEqual(dinheiro.valor, Decimal("10.50"))

    def test_dinheiro_rejeita_valor_negativo(self):
        with self.assertRaises(ValorMonetarioInvalidoError):
            Dinheiro("-0.01")
