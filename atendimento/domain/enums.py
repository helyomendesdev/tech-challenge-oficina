"""Enums puros do dominio de atendimento.

Centralizam a linguagem ubíqua do DDD sem depender de Django ou DRF. Os valores
preservam os status ja expostos pelos endpoints e persistidos nos models.
"""

from enum import Enum


class StatusOrdemServico(str, Enum):
    """Status de uma ordem de servico na oficina."""

    RECEBIDA = "RECEBIDA"
    DIAGNOSTICO = "DIAGNOSTICO"
    AGUARDANDO = "AGUARDANDO"
    EXECUCAO = "EXECUCAO"
    FINALIZADA = "FINALIZADA"
    ENTREGUE = "ENTREGUE"
    CANCELADA = "CANCELADA"


class StatusItemServico(str, Enum):
    """Status de um item de servico vinculado a uma ordem de servico."""

    PENDENTE = "PENDENTE"
    EM_EXECUCAO = "EM_EXECUCAO"
    CONCLUIDO = "CONCLUIDO"


class DecisaoOrcamento(str, Enum):
    """Decisoes possiveis para processamento de um orcamento."""

    APROVADO = "APROVADO"
    RECUSADO = "RECUSADO"
