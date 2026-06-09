"""Adapter de infraestrutura para servicos via Django ORM.

Implementa ServicoRepositoryPort e valida a existencia dos servicos solicitados
antes de entregar dados aos use cases.
"""

from atendimento.application.ports.servico_repository import ServicoRepositoryPort
from atendimento.domain.exceptions import DomainError
from atendimento.models import Servico


class DjangoServicoRepository(ServicoRepositoryPort):
    """Repository concreto de servicos usando Django ORM."""

    def get_by_ids(
        self,
        ids: list[int],
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> list[Servico]:
        """Busca servicos pelos ids informados, preservando a ordem solicitada."""
        queryset = Servico.objects.filter(id__in=ids)
        if not usuario_is_staff:
            if usuario_id is None and ids:
                raise DomainError("Servico nao encontrado ou inacessivel.")
            queryset = queryset.filter(created_by_id=usuario_id)

        servicos = list(queryset)
        servicos_por_id = {servico.id: servico for servico in servicos}
        ids_nao_encontrados = [
            servico_id for servico_id in ids if servico_id not in servicos_por_id
        ]

        if ids_nao_encontrados:
            raise DomainError(
                f"Servicos nao encontrados: {', '.join(map(str, ids_nao_encontrados))}."
            )

        return [servicos_por_id[servico_id] for servico_id in ids]
