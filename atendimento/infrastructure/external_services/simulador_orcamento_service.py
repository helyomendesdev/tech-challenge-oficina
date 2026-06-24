import requests


class SimuladorOrcamentoService:
    """
    Simula um sistema externo responsável pela aprovação ou recusa
    de orçamentos de clientes.

    Este serviço representa um consumidor externo da API da oficina.
    Ele realiza uma chamada HTTP real para o webhook de notificações
    de orçamento, enviando a decisão tomada pelo cliente.

    Fluxo simulado:

        Cliente
          |
          v
        SimuladorOrcamentoService
          |
          | HTTP POST
          v
        Webhook da API Oficina
          |
          v
        ProcessarRespostaOrcamentoUseCase

    Observação:
        Este serviço existe apenas para simular uma integração externa.
        O FakeNotificationAdapter continua sendo utilizado como fallback
        nos fluxos internos da aplicação.
    """

    def enviar_decisao(
        self,
        ordem_servico_id: int,
        decisao: str,
        motivo: str = "",
        authorization: str | None = None,
    ):
        payload = {
            "ordem_servico_id": ordem_servico_id,
            "decisao": decisao,
            "origem": "simulador_cliente",
            "motivo": motivo,
        }

        headers = {}

        if authorization:
            headers["Authorization"] = authorization

        response = requests.post(
            "http://localhost:8000/api/v1/orcamentos/notificacoes/",
            json=payload,
            headers=headers,
            timeout=5,
        )

        response.raise_for_status()

        return response.json()
