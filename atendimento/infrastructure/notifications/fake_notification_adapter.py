"""Adaptador fake de notificacoes.

Pode ser usado em desenvolvimento ou em use cases iniciais para preservar o
fluxo sem integrar um provedor externo real.
"""

from typing import Any

from atendimento.application.ports.notification_port import NotificationPort


class FakeNotificationAdapter(NotificationPort):
    """Adaptador de notificacao que simula envios sem e-mail real."""

    def notificar_orcamento(
        self, ordem_servico_id: int, email: str, valor_total: Any
    ) -> dict[str, Any]:
        """Simula o envio de notificacao de orcamento."""
        return {
            "enviado": True,
            "tipo": "orcamento",
            "ordem_servico_id": ordem_servico_id,
            "email": email,
            "valor_total": valor_total,
        }

    def notificar_conclusao(
        self, ordem_servico_id: int, email: str
    ) -> dict[str, Any]:
        """Simula o envio de notificacao de conclusao."""
        return {
            "enviado": True,
            "tipo": "conclusao",
            "ordem_servico_id": ordem_servico_id,
            "email": email,
        }
