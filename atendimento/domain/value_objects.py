"""Value Objects puros do dominio.

Representam conceitos pequenos do negocio, normalizando e validando invariantes
sem conhecer serializers, models, request ou banco de dados.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

from validate_docbr import CNPJ, CPF

from atendimento.domain.exceptions import (
    DocumentoInvalidoError,
    PlacaInvalidaError,
    QuantidadeInvalidaError,
    ValorMonetarioInvalidoError,
)


@dataclass(frozen=True)
class DocumentoCliente:
    """CPF ou CNPJ normalizado apenas com digitos."""

    valor: str

    def __post_init__(self):
        documento = re.sub(r"\D", "", str(self.valor or ""))

        if len(documento) not in (11, 14):
            raise DocumentoInvalidoError(
                "Documento deve ter 11 digitos para CPF ou 14 digitos para CNPJ."
            )

        if len(documento) == 11 and not CPF().validate(documento):
            raise DocumentoInvalidoError("CPF invalido.")

        if len(documento) == 14 and not CNPJ().validate(documento):
            raise DocumentoInvalidoError("CNPJ invalido.")

        object.__setattr__(self, "valor", documento)

    def __str__(self):
        return self.valor


@dataclass(frozen=True)
class PlacaVeiculo:
    """Placa de veiculo normalizada em maiusculas."""

    valor: str

    def __post_init__(self):
        placa = str(self.valor or "").strip().upper()

        if not re.match(r"^[A-Z]{3}\d[A-Z\d]\d{2}$", placa):
            raise PlacaInvalidaError("Placa em formato invalido.")

        object.__setattr__(self, "valor", placa)

    def __str__(self):
        return self.valor


@dataclass(frozen=True)
class Quantidade:
    """Quantidade inteira positiva."""

    valor: int

    def __post_init__(self):
        if isinstance(self.valor, bool):
            raise QuantidadeInvalidaError(
                "Quantidade deve ser um numero inteiro maior que zero."
            )

        try:
            quantidade_decimal = Decimal(str(self.valor))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise QuantidadeInvalidaError(
                "Quantidade deve ser um numero inteiro maior que zero."
            ) from exc

        if (
            not quantidade_decimal.is_finite()
            or quantidade_decimal != quantidade_decimal.to_integral_value()
            or quantidade_decimal <= 0
        ):
            raise QuantidadeInvalidaError(
                "Quantidade deve ser um numero inteiro maior que zero."
            )

        object.__setattr__(self, "valor", int(quantidade_decimal))

    def __int__(self):
        return self.valor


@dataclass(frozen=True)
class Dinheiro:
    """Valor monetario nao negativo representado com Decimal."""

    valor: Decimal

    def __post_init__(self):
        try:
            valor = Decimal(str(self.valor))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValorMonetarioInvalidoError(
                "Valor monetario deve ser um numero decimal valido."
            ) from exc

        if not valor.is_finite():
            raise ValorMonetarioInvalidoError(
                "Valor monetario deve ser um numero decimal valido."
            )

        if valor < 0:
            raise ValorMonetarioInvalidoError(
                "Valor monetario nao pode ser negativo."
            )

        object.__setattr__(self, "valor", valor)

    def __str__(self):
        return str(self.valor)
