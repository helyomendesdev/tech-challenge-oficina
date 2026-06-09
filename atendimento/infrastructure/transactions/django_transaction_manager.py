"""Transaction manager baseado em Django.

Implementa o port TransactionManagerPort usando django.db.transaction.atomic.
"""

from django.db import transaction

from atendimento.application.ports.transaction_manager import TransactionManagerPort


class DjangoTransactionManager(TransactionManagerPort):
    """Transaction manager concreto usando Django."""

    def atomic(self):
        """Retorna o context manager transacional do Django."""
        return transaction.atomic()
