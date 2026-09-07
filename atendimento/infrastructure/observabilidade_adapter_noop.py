"""No-op adapter de observabilidade — desabilitado.

Implementa ObservabilidadePort como no-operation. Usado como padrão nos use cases
para não quebrar testes existentes quando observabilidade_port não é injetado.
"""

from typing import Any


class ObservabilidadeAdapterNoop:
    """No-op adapter para observabilidade — desabilitado por padrão.

    Implementa o contrato de ObservabilidadePort mas não faz nada,
    permitindo que use cases rodem sem quebrar quando nenhuma observabilidade
    é configurada (cenário padrão de testes).
    """

    def registrar_evento_ordem_servico(self, evento_dict: dict[str, Any]) -> None:
        """No-op: não registra nada.

        Args:
            evento_dict: Ignorado
        """
        pass
