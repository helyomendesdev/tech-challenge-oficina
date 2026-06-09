"""Port de gerenciamento transacional.

Define o contrato usado pelos use cases para executar operações atômicas sem
depender diretamente de django.db.transaction.
"""

from typing import Any, Protocol


class TransactionManagerPort(Protocol):
    """Contrato para controle de transacoes."""

    def atomic(self) -> Any:
        """Retorna um context manager transacional."""
