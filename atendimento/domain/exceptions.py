"""Exceptions de dominio.

Use este modulo para erros ligados a regras de negocio, invariantes e
transicoes invalidas. Essas exceptions devem ser independentes de DRF.
"""


class DomainError(Exception):
    """Erro base para violacoes de regra de negocio do dominio."""


class TransicaoStatusInvalidaError(DomainError):
    """Erro para transicoes de status nao permitidas pelo dominio."""


class EstoqueInsuficienteError(DomainError):
    """Erro para operacoes que tentam consumir estoque insuficiente."""


class OrdemServicoNaoEncontradaError(DomainError):
    """Erro para ordem de servico inexistente ou inacessivel no fluxo atual."""


class PecaNaoPertenceOrdemServicoError(DomainError):
    """Erro para peca que nao pertence a ordem de servico informada."""


class QuantidadeIndisponivelError(DomainError):
    """Erro para quantidades invalidas ou indisponiveis no dominio."""


class RegraFinalizacaoOrdemServicoError(DomainError):
    """Erro para violacoes das regras de finalizacao da ordem de servico."""


class OrcamentoNaoPodeSerProcessadoError(DomainError):
    """Erro para orcamentos que nao podem ser aprovados ou recusados."""


class DocumentoInvalidoError(DomainError):
    """Erro para CPF ou CNPJ invalido."""


class PlacaInvalidaError(DomainError):
    """Erro para placa de veiculo invalida."""


class QuantidadeInvalidaError(DomainError):
    """Erro para quantidade inteira invalida."""


class ValorMonetarioInvalidoError(DomainError):
    """Erro para valor monetario invalido."""
