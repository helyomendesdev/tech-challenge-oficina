"""Adapter de infraestrutura para pecas via Django ORM.

Implementa PecaRepositoryPort e centraliza acesso a pecas, preservando a regra
legada de baixa de estoque em ItemPecaOS nesta fase.
"""

from atendimento.application.ports.peca_repository import PecaRepositoryPort
from atendimento.domain.exceptions import DomainError
from atendimento.models import Peca


class DjangoPecaRepository(PecaRepositoryPort):
    """Repository concreto de pecas usando Django ORM."""

    def get_by_id(self, peca_id: int) -> Peca:
        """Busca uma peca pelo id."""
        try:
            return Peca.objects.get(id=peca_id)
        except Peca.DoesNotExist as exc:
            raise DomainError("Peca nao encontrada.") from exc
