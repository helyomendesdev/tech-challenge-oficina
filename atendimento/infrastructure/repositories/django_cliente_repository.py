"""Adapter de infraestrutura para clientes via Django ORM.

Implementa ClienteRepositoryPort e traduz detalhes de persistencia para a
camada de aplicacao, mantendo models.py no local atual.
"""

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError

from atendimento.application.ports.cliente_repository import ClienteRepositoryPort
from atendimento.domain.exceptions import DomainError
from atendimento.models import Cliente


def _campo(dados: Any, nome: str) -> Any:
    if isinstance(dados, dict):
        return dados.get(nome)
    return getattr(dados, nome)


class DjangoClienteRepository(ClienteRepositoryPort):
    """Repository concreto de clientes usando Django ORM."""

    def get_by_documento(self, documento: str) -> Cliente:
        """Busca um cliente pelo documento."""
        try:
            return Cliente.objects.get(documento=documento)
        except Cliente.DoesNotExist as exc:
            raise DomainError("Cliente nao encontrado.") from exc

    def get_or_create(
        self,
        dados_cliente: Any,
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> Cliente:
        """Busca ou cria um cliente pelo documento."""
        defaults = {
            "nome": _campo(dados_cliente, "nome"),
            "email": _campo(dados_cliente, "email"),
            "telefone": _campo(dados_cliente, "telefone"),
        }
        if usuario_id is not None:
            defaults["created_by_id"] = usuario_id

        documento = str(_campo(dados_cliente, "documento"))
        try:
            cliente = Cliente.objects.get(documento=documento)
            if not usuario_is_staff and (
                usuario_id is None or cliente.created_by_id != usuario_id
            ):
                raise DomainError("Cliente nao encontrado ou inacessivel.")
            return cliente
        except Cliente.DoesNotExist:
            pass
        except DomainError:
            raise

        try:
            return Cliente.objects.create(documento=documento, **defaults)
        except (DjangoValidationError, IntegrityError) as exc:
            raise DomainError(
                f"Nao foi possivel obter ou criar cliente: {exc}"
            ) from exc
