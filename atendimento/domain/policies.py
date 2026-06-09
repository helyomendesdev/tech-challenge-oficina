"""Policies puras de dominio.

Encapsulam regras de negocio e decisoes taticas do DDD, como transicoes de
status e finalizacao de OS, sem acessar Django ORM, DRF ou request.
"""

from .enums import StatusItemServico, StatusOrdemServico
from .exceptions import (
    RegraFinalizacaoOrdemServicoError,
    TransicaoStatusInvalidaError,
)


def _valor(valor):
    """Retorna o valor bruto de enums, strings ou atributos simples."""
    return getattr(valor, "value", valor)


def _obter_campo(objeto, campo):
    """Busca um campo em objetos simples ou dicionarios."""
    if isinstance(objeto, dict):
        return objeto.get(campo)
    return getattr(objeto, campo)


class OrdemServicoStatusPolicy:
    """Valida transicoes de status da ordem de servico."""

    TRANSICOES_VALIDAS = {
        StatusOrdemServico.RECEBIDA.value: {StatusOrdemServico.DIAGNOSTICO.value},
        StatusOrdemServico.DIAGNOSTICO.value: {StatusOrdemServico.AGUARDANDO.value},
        StatusOrdemServico.AGUARDANDO.value: {
            StatusOrdemServico.EXECUCAO.value,
            StatusOrdemServico.DIAGNOSTICO.value,
            StatusOrdemServico.CANCELADA.value,
        },
        StatusOrdemServico.EXECUCAO.value: {StatusOrdemServico.FINALIZADA.value},
        StatusOrdemServico.FINALIZADA.value: {StatusOrdemServico.ENTREGUE.value},
        StatusOrdemServico.ENTREGUE.value: set(),
        StatusOrdemServico.CANCELADA.value: set(),
    }

    @classmethod
    def validar_transicao(cls, status_atual, novo_status):
        """Valida se a transicao informada e permitida pelo dominio."""
        status_atual = _valor(status_atual)
        novo_status = _valor(novo_status)

        transicoes_possiveis = cls.TRANSICOES_VALIDAS.get(status_atual, set())
        if novo_status not in transicoes_possiveis:
            raise TransicaoStatusInvalidaError(
                f"Transicao de status invalida: {status_atual} -> {novo_status}."
            )


class FilaOrdemServicoPolicy:
    """Define visibilidade e prioridade da fila operacional de ordens."""

    PRIORIDADES = {
        StatusOrdemServico.EXECUCAO.value: 1,
        StatusOrdemServico.AGUARDANDO.value: 2,
        StatusOrdemServico.DIAGNOSTICO.value: 3,
        StatusOrdemServico.RECEBIDA.value: 4,
    }
    STATUS_VISIVEIS = tuple(PRIORIDADES.keys())

    @classmethod
    def deve_aparecer_na_fila(cls, status):
        """Indica se a ordem deve aparecer na fila operacional."""
        return _valor(status) in cls.STATUS_VISIVEIS

    @classmethod
    def prioridade(cls, status):
        """Retorna a prioridade operacional do status informado."""
        return cls.PRIORIDADES.get(_valor(status))


class FinalizacaoOrdemServicoPolicy:
    """Valida se uma ordem de servico pode ser finalizada."""

    @classmethod
    def validar_finalizacao(cls, status_ordem_servico, itens_servico, itens_pecas):
        """Valida todas as regras necessarias para finalizar uma ordem."""
        if _valor(status_ordem_servico) != StatusOrdemServico.EXECUCAO.value:
            raise RegraFinalizacaoOrdemServicoError(
                "A OS precisa estar em EXECUCAO para ser finalizada."
            )

        if not cls.todos_servicos_concluidos(itens_servico):
            raise RegraFinalizacaoOrdemServicoError(
                "Nao e possivel finalizar a OS: existem servicos nao concluidos."
            )

        if not cls.todas_pecas_utilizadas(itens_pecas):
            raise RegraFinalizacaoOrdemServicoError(
                "Nao e possivel finalizar a OS: existem pecas nao utilizadas."
            )

    @classmethod
    def todos_servicos_concluidos(cls, itens_servico):
        """Indica se todos os itens de servico estao concluidos."""
        return all(
            _valor(_obter_campo(item, "status")) == StatusItemServico.CONCLUIDO.value
            for item in itens_servico
        )

    @classmethod
    def todas_pecas_utilizadas(cls, itens_pecas):
        """Indica se todas as pecas reservadas foram utilizadas."""
        return all(
            _obter_campo(item, "quantidade_utilizada") == _obter_campo(item, "quantidade")
            for item in itens_pecas
        )
