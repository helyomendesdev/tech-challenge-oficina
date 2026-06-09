"""Port de repository de clientes.

Contrato hexagonal usado pelos use cases para acessar clientes sem conhecer o
ORM, banco de dados ou framework web.
"""

from typing import Any, Protocol


class ClienteRepositoryPort(Protocol):
    """Contrato para acesso a clientes."""

    def get_by_documento(self, documento: str) -> Any:
        """Busca um cliente pelo documento."""

    def get_or_create(
        self,
        dados_cliente: Any,
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> Any:
        """Busca ou cria um cliente a partir dos dados informados."""
