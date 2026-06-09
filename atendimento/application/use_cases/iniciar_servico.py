"""Use case de inicio de execucao de um item de servico da OS.

Camada de aplicacao: preserva o fluxo legado de consumo de pecas usando ports
e transacao, sem depender de ViewSet, serializers ou Django ORM.
"""

from typing import Any

from atendimento.application.dtos import IniciarServicoInputDTO
from atendimento.application.ports.ordem_servico_repository import (
    ItemServicoRepositoryPort,
)
from atendimento.application.ports.transaction_manager import TransactionManagerPort
from atendimento.domain.enums import StatusItemServico, StatusOrdemServico
from atendimento.domain.exceptions import (
    QuantidadeIndisponivelError,
    TransicaoStatusInvalidaError,
)


def _campo(objeto: Any, nome: str) -> Any:
    """Busca um campo em objetos simples ou dicionarios."""
    if isinstance(objeto, dict):
        return objeto.get(nome)
    return getattr(objeto, nome)


class IniciarServicoUseCase:
    """Orquestra o inicio de execucao de um item de servico da OS."""

    def __init__(
        self,
        ordem_servico_repository: ItemServicoRepositoryPort,
        transaction_manager: TransactionManagerPort,
    ):
        self.ordem_servico_repository = ordem_servico_repository
        self.transaction_manager = transaction_manager

    def execute(self, input_dto: IniciarServicoInputDTO) -> Any:
        """Executa o inicio do servico preservando as regras atuais."""
        with self.transaction_manager.atomic():
            item_servico = self.ordem_servico_repository.get_item_servico(
                input_dto.ordem_servico_id,
                input_dto.item_servico_id,
                usuario_id=input_dto.usuario_id,
                usuario_is_staff=input_dto.usuario_is_staff,
            )

            if _campo(item_servico, "status") != StatusItemServico.PENDENTE.value:
                raise TransicaoStatusInvalidaError(
                    "Servico ja foi iniciado ou concluido"
                )

            ordem_servico = _campo(item_servico, "ordem_servico")
            if _campo(ordem_servico, "status") != StatusOrdemServico.EXECUCAO.value:
                raise TransicaoStatusInvalidaError(
                    "A OS precisa estar em EXECUCAO para iniciar servicos."
                )

            item_peca_por_id = {}
            quantidade_por_item_peca = {}
            for entrada in input_dto.pecas:
                item_peca_os_id = entrada["item_peca_os_id"]
                quantidade = entrada["quantidade"]

                if quantidade <= 0:
                    raise QuantidadeIndisponivelError(
                        "Quantidade consumida deve ser maior que zero"
                    )

                item_peca = item_peca_por_id.get(item_peca_os_id)
                if item_peca is None:
                    item_peca = self.ordem_servico_repository.get_item_peca(
                        input_dto.ordem_servico_id,
                        item_peca_os_id,
                    )
                    item_peca_por_id[item_peca_os_id] = item_peca

                disponivel = (
                    _campo(item_peca, "quantidade")
                    - _campo(item_peca, "quantidade_utilizada")
                )
                quantidade_total = (
                    quantidade_por_item_peca.get(item_peca_os_id, 0) + quantidade
                )
                if quantidade_total > disponivel:
                    peca = _campo(item_peca, "peca")
                    raise QuantidadeIndisponivelError(
                        f"Quantidade indisponível para '{_campo(peca, 'nome')}'. "
                        f"Disponível: {disponivel}, solicitado: {quantidade_total}"
                    )

                quantidade_por_item_peca[item_peca_os_id] = quantidade_total

            for item_peca_os_id, quantidade in quantidade_por_item_peca.items():
                item_peca = item_peca_por_id[item_peca_os_id]
                # Consumo usa a reserva da OS; estoque fisico ja foi baixado
                # uma unica vez na criacao/alteracao de ItemPecaOS.
                self.ordem_servico_repository.criar_consumo_item_servico(
                    item_servico,
                    item_peca,
                    quantidade,
                )
                self.ordem_servico_repository.atualizar_quantidade_utilizada_item_peca(
                    item_peca,
                    quantidade,
                )

            return self.ordem_servico_repository.iniciar_item_servico(
                item_servico,
                input_dto.data_inicio,
            )
