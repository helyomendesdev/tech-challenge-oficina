"""Port de observabilidade — emissão de custom events.

Contrato de saída para que use cases emitam eventos de negócio (§5.4 da spec)
sem acoplar a New Relic, CloudWatch, Datadog ou outro provedor de observabilidade.
"""

from typing import Any, Protocol, Optional


class ObservabilidadePort(Protocol):
    """Contrato para adaptadores de observabilidade — emissão de eventos de negócio.

    Um evento de negócio documenta a transição de status de uma ordem de serviço,
    permitindo medir volume diário, tempo médio por status, e falhas no processamento.
    """

    def registrar_evento_ordem_servico(self, evento_dict: dict[str, Any]) -> None:
        """Registra um evento de transição de status de ordem de serviço.

        Args:
            evento_dict: Dicionário com os campos do evento (§5.4):
                - evento (str): ABERTURA | TRANSICAO | CONCLUSAO | FALHA
                - osId (int): Identificador da OS
                - statusAnterior (str | None): Status anterior (None para ABERTURA)
                - statusNovo (str): Novo status (RECEBIDA, DIAGNOSTICO, AGUARDANDO_APROVACAO, EXECUCAO, FINALIZADA, ENTREGUE)
                - duracaoStatusSegundos (float): Tempo em segundos no status anterior
                - erroTipo (str | None): Tipo de erro (preenchido só quando evento = FALHA)
                - traceId (str): ID do trace W3C para correlação com logs

        Regras de segurança:
        - Nunca registrar CPF, email, telefone ou PII em claro
        - Nunca registrar `unidade`: o campo nao existe no modelo nem na API (ver §5.4
          da spec). Emitir valor fixo faria D1 facetar tudo numa unidade inventada.
        - O identificador de cliente deve ir como hash se necessário
        """
