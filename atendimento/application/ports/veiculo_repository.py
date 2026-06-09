"""Port de repository de veiculos.

Contrato hexagonal usado pelos use cases para acessar veiculos sem depender de
Django ORM, serializers ou infraestrutura concreta.
"""

from typing import Any, Protocol


class VeiculoRepositoryPort(Protocol):
    """Contrato para acesso a veiculos."""

    def get_by_placa(self, placa: str) -> Any:
        """Busca um veiculo pela placa."""

    def get_or_create(
        self,
        cliente: Any,
        dados_veiculo: Any,
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> Any:
        """Busca ou cria um veiculo vinculado ao cliente informado."""
