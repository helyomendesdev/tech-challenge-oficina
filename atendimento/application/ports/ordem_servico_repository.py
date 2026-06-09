"""Port de repository de ordens de servico.

Contrato central da arquitetura hexagonal para que use cases manipulem OS,
itens e fila sem conhecer QuerySet, models ou banco de dados.
"""

from typing import Any, Protocol


class OrdemServicoConsultaPort(Protocol):
    """Contrato para consultas de ordens de servico."""

    def get_by_id(self, ordem_servico_id: int) -> Any:
        """Busca uma ordem de servico pelo id."""

    def get_by_id_for_user(
        self,
        ordem_servico_id: int,
        usuario_id: int | None,
        usuario_is_staff: bool,
    ) -> Any:
        """Busca uma ordem considerando isolamento por usuario."""

    def consultar_status(
        self,
        ordem_servico_id: int,
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> Any:
        """Consulta o status de uma ordem considerando contexto de usuario."""

    def consultar_status_for_user(
        self,
        ordem_servico_id: int,
        usuario_id: int | None,
        usuario_is_staff: bool,
    ) -> Any:
        """Consulta o status de uma ordem considerando isolamento por usuario."""


class OrdemServicoEscritaPort(Protocol):
    """Contrato para escrita de ordens de servico e seus itens."""

    def create(self, cliente: Any, veiculo: Any, usuario_id: int | None = None) -> Any:
        """Cria uma ordem de servico."""

    def adicionar_servicos(
        self, ordem_servico: Any, servicos: list[Any], usuario_id: int | None = None
    ) -> None:
        """Adiciona servicos a uma ordem de servico."""

    def adicionar_pecas(
        self,
        ordem_servico: Any,
        pecas_input: list[Any],
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> None:
        """Adiciona pecas a uma ordem de servico."""

    def recalcular_total(self, ordem_servico: Any) -> Any:
        """Recalcula o valor total da ordem de servico."""

    def save(self, ordem_servico: Any) -> Any:
        """Persiste alteracoes na ordem de servico."""


class OrdemServicoFilaPort(Protocol):
    """Contrato para listagem da fila operacional."""

    def listar_fila_operacional(
        self,
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> list[Any]:
        """Lista ordens da fila operacional considerando contexto de usuario."""

    def listar_fila_operacional_for_user(
        self,
        usuario_id: int | None,
        usuario_is_staff: bool,
    ) -> list[Any]:
        """Lista ordens da fila operacional considerando isolamento por usuario."""


class ItemServicoRepositoryPort(Protocol):
    """Contrato para itens de servico e consumos vinculados a uma OS."""

    def get_item_servico(
        self,
        ordem_servico_id: int,
        item_servico_id: int,
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> Any:
        """Busca um item de servico vinculado a uma ordem de servico."""

    def get_item_peca(self, ordem_servico_id: int, item_peca_os_id: int) -> Any:
        """Busca um item de peca vinculado a uma ordem de servico."""

    def criar_consumo_item_servico(
        self, item_servico: Any, item_peca: Any, quantidade: int
    ) -> Any:
        """Cria o consumo de uma peca por um item de servico."""

    def atualizar_quantidade_utilizada_item_peca(
        self, item_peca: Any, quantidade: int
    ) -> Any:
        """Incrementa a quantidade utilizada de uma peca da ordem."""

    def iniciar_item_servico(
        self, item_servico: Any, data_inicio: Any
    ) -> Any:
        """Marca um item de servico como em execucao."""

    def finalizar_item_servico(
        self, item_servico: Any, data_finalizacao: Any
    ) -> Any:
        """Marca um item de servico como concluido."""


class OrdemServicoFinalizacaoPort(Protocol):
    """Contrato para gates e conclusao de uma ordem de servico."""

    def existem_servicos_nao_concluidos(self, ordem_servico: Any) -> bool:
        """Indica se a ordem possui servicos ainda nao concluidos."""

    def existem_pecas_nao_utilizadas(self, ordem_servico: Any) -> bool:
        """Indica se a ordem possui pecas reservadas nao utilizadas."""

    def possui_servico_nao_concluido(self, ordem_servico: Any) -> bool:
        """Indica se a ordem possui ao menos um servico nao concluido."""

    def possui_peca_nao_utilizada(self, ordem_servico: Any) -> bool:
        """Indica se a ordem possui ao menos uma peca reservada nao utilizada."""

    def pode_finalizar(self, ordem_servico: Any) -> bool:
        """Indica se a ordem atende aos gates de finalizacao."""

    def validar_finalizacao(
        self,
        ordem_servico: Any,
        status_atual: str | None = None,
    ) -> None:
        """Valida os gates de finalizacao sem expor detalhes de persistencia."""

    def finalizar_ordem_servico(
        self, ordem_servico: Any, data_finalizacao: Any
    ) -> Any:
        """Marca uma ordem de servico como finalizada."""


class OrdemServicoRepositoryPort(
    OrdemServicoConsultaPort,
    OrdemServicoEscritaPort,
    OrdemServicoFilaPort,
    ItemServicoRepositoryPort,
    OrdemServicoFinalizacaoPort,
    Protocol,
):
    """Contrato composto para adapters que suportam o fluxo completo de OS."""
