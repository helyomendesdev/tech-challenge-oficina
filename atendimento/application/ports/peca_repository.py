"""Port de repository de pecas.

Contrato hexagonal para acesso a pecas pela aplicacao, mantendo regras de fluxo
independentes do ORM e da persistencia concreta.
"""

from typing import Any, Protocol


class PecaRepositoryPort(Protocol):
    """Contrato para acesso a pecas."""

    def get_by_id(self, peca_id: int) -> Any:
        """Busca uma peca pelo id."""
