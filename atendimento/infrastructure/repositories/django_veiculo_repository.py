"""Adapter de infraestrutura para veiculos via Django ORM.

Implementa VeiculoRepositoryPort e isola consultas, criacao e conflitos de
placa dos use cases.
"""

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError

from atendimento.application.ports.veiculo_repository import VeiculoRepositoryPort
from atendimento.domain.exceptions import DomainError
from atendimento.models import Veiculo


def _campo(dados: Any, nome: str) -> Any:
    if isinstance(dados, dict):
        return dados.get(nome)
    return getattr(dados, nome)


class DjangoVeiculoRepository(VeiculoRepositoryPort):
    """Repository concreto de veiculos usando Django ORM."""

    def get_by_placa(self, placa: str) -> Veiculo:
        """Busca um veiculo pela placa."""
        try:
            return Veiculo.objects.get(placa=placa)
        except Veiculo.DoesNotExist as exc:
            raise DomainError("Veiculo nao encontrado.") from exc

    def get_or_create(
        self,
        cliente: Any,
        dados_veiculo: Any,
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> Veiculo:
        """Busca ou cria um veiculo pela placa."""
        defaults = {
            "cliente": cliente,
            "marca": _campo(dados_veiculo, "marca"),
            "modelo": _campo(dados_veiculo, "modelo"),
            "ano": _campo(dados_veiculo, "ano"),
        }
        if usuario_id is not None:
            defaults["created_by_id"] = usuario_id

        placa = str(_campo(dados_veiculo, "placa")).upper()
        try:
            veiculo = Veiculo.objects.get(placa=placa)
        except Veiculo.DoesNotExist:
            try:
                return Veiculo.objects.create(placa=placa, **defaults)
            except (DjangoValidationError, IntegrityError) as exc:
                raise DomainError(
                    f"Nao foi possivel obter ou criar veiculo: {exc}"
                ) from exc

        if not usuario_is_staff and (
            usuario_id is None or veiculo.created_by_id != usuario_id
        ):
            raise DomainError("Veiculo nao encontrado ou inacessivel.")

        if veiculo.cliente_id != cliente.id:
            raise DomainError("Placa ja cadastrada para outro cliente.")

        return veiculo
