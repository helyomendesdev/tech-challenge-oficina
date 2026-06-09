"""Port de notificacoes.

Contrato de saida para que use cases solicitem notificacoes sem acoplar a
e-mail, fila, webhook ou outro provedor externo.
"""

from typing import Any, Protocol


class NotificationPort(Protocol):
    """Contrato para adaptadores de notificacao."""

    def notificar_orcamento(
        self, ordem_servico_id: int, email: str, valor_total: Any
    ) -> dict[str, Any]:
        """Notifica o cliente sobre o orcamento da ordem de servico."""

    def notificar_conclusao(self, ordem_servico_id: int, email: str) -> dict[str, Any]:
        """Notifica o cliente sobre a conclusao da ordem de servico."""
