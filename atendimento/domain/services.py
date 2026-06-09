"""Services puros de dominio.

Use services de dominio quando uma regra de negocio cruza mais de um conceito
e nao pertence naturalmente a um value object ou policy especifica.
Este modulo nao acessa Django, DRF, ORM ou qualquer detalhe de infraestrutura.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

from atendimento.domain.exceptions import (
    EstoqueInsuficienteError,
    QuantidadeIndisponivelError,
    ValorMonetarioInvalidoError,
)
from atendimento.domain.value_objects import Dinheiro, Quantidade


def _campo(objeto: Any, nome: str, padrao: Any = None) -> Any:
    """Busca um campo em objetos simples ou dicionarios."""
    if isinstance(objeto, dict):
        return objeto.get(nome, padrao)
    return getattr(objeto, nome, padrao)


def _decimal(valor: Any) -> Decimal:
    """Normaliza valores numericos sem depender de frameworks."""
    try:
        decimal = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValorMonetarioInvalidoError(
            "Valor monetario deve ser um numero decimal valido."
        ) from exc

    if not decimal.is_finite():
        raise ValorMonetarioInvalidoError(
            "Valor monetario deve ser um numero decimal valido."
        )
    return decimal


class OrcamentoDomainService:
    """Calcula o valor conceitual de uma ordem de servico.

    O service aceita objetos simples ou dicionarios para manter o dominio
    independente do Django ORM. Servicos devem expor `valor_mao_de_obra`.
    Pecas podem expor `total_item` ou o par `valor_unitario` + `quantidade`.
    """

    @classmethod
    def calcular_total(cls, servicos=None, pecas=None) -> Dinheiro:
        """Retorna o total de servicos e pecas como value object `Dinheiro`."""
        total_servicos = sum(
            _decimal(_campo(servico, "valor_mao_de_obra", 0))
            for servico in (servicos or [])
        )
        total_pecas = sum(cls._total_peca(peca) for peca in (pecas or []))
        return Dinheiro(total_servicos + total_pecas)

    @staticmethod
    def _total_peca(peca: Any) -> Decimal:
        total_item = _campo(peca, "total_item")
        if total_item is not None:
            return _decimal(total_item)

        quantidade = Quantidade(_campo(peca, "quantidade")).valor
        valor_unitario = _decimal(_campo(peca, "valor_unitario"))
        return valor_unitario * quantidade


class EstoqueDomainService:
    """Valida disponibilidade e consumo de estoque sem acessar persistencia."""

    @staticmethod
    def validar_disponibilidade(
        estoque_atual: int,
        quantidade_solicitada: int,
        nome_peca: str = "peca",
    ) -> None:
        """Garante que ha estoque suficiente para uma reserva."""
        quantidade = Quantidade(quantidade_solicitada).valor
        estoque = EstoqueDomainService._normalizar_estoque(estoque_atual)

        if estoque < quantidade:
            raise EstoqueInsuficienteError(
                f"Estoque insuficiente para '{nome_peca}'. "
                f"Disponivel: {estoque}, solicitado: {quantidade}."
            )

    @staticmethod
    def validar_consumo_disponivel(
        quantidade_reservada: int,
        quantidade_utilizada: int,
        quantidade_solicitada: int,
        nome_peca: str = "peca",
    ) -> None:
        """Garante que o consumo nao excede a quantidade reservada restante."""
        reservada = Quantidade(quantidade_reservada).valor
        utilizada = EstoqueDomainService._normalizar_quantidade_utilizada(
            quantidade_utilizada
        )
        solicitada = Quantidade(quantidade_solicitada).valor
        disponivel = reservada - utilizada

        if disponivel < solicitada:
            raise QuantidadeIndisponivelError(
                f"Quantidade indisponivel para '{nome_peca}'. "
                f"Disponivel: {disponivel}, solicitado: {solicitada}."
            )

    @staticmethod
    def _normalizar_estoque(estoque_atual: int) -> int:
        if isinstance(estoque_atual, bool):
            raise QuantidadeIndisponivelError(
                "Estoque atual deve ser um numero inteiro maior ou igual a zero."
            )

        try:
            estoque = int(estoque_atual)
        except (TypeError, ValueError) as exc:
            raise QuantidadeIndisponivelError(
                "Estoque atual deve ser um numero inteiro maior ou igual a zero."
            ) from exc

        if estoque < 0:
            raise QuantidadeIndisponivelError(
                "Estoque atual deve ser um numero inteiro maior ou igual a zero."
            )
        return estoque

    @staticmethod
    def _normalizar_quantidade_utilizada(quantidade_utilizada: int) -> int:
        if isinstance(quantidade_utilizada, bool):
            raise QuantidadeIndisponivelError(
                "Quantidade utilizada deve ser um numero inteiro maior ou igual a zero."
            )

        try:
            utilizada = int(quantidade_utilizada)
        except (TypeError, ValueError) as exc:
            raise QuantidadeIndisponivelError(
                "Quantidade utilizada deve ser um numero inteiro maior ou igual a zero."
            ) from exc

        if utilizada < 0:
            raise QuantidadeIndisponivelError(
                "Quantidade utilizada deve ser um numero inteiro maior ou igual a zero."
            )
        return utilizada
