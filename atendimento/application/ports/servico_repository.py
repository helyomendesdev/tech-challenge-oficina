"""Port de repository de servicos.

Contrato hexagonal para consulta de servicos pela camada de aplicacao sem
acoplamento ao ORM ou a models Django.
"""

from typing import Any, Protocol


class ServicoRepositoryPort(Protocol):
    """Contrato para acesso a servicos."""

    def get_by_ids(
        self,
        ids: list[int],
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> list[Any]:
        """Busca servicos pelos ids informados."""
