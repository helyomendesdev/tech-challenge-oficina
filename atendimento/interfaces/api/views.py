"""Views da interface API da Fase 2.

Adapters de entrada HTTP/DRF. Recebem request, validam serializers, chamam use
cases por factories e traduzem DTOs/erros para responses. Mantem as views finas
enquanto os ViewSets legados continuam atendendo endpoints da Fase 1.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)

from atendimento.domain.exceptions import (
    DomainError,
)
from atendimento.exceptions import response_from_domain_error
from atendimento.infrastructure.factories import (
    build_abrir_ordem_servico_use_case,
    build_atualizar_status_por_notificacao_use_case,
    build_consultar_status_ordem_servico_use_case,
    build_listar_fila_ordens_servico_use_case,
    build_processar_resposta_orcamento_use_case,
    build_simulador_orcamento_service,
)
from atendimento.interfaces.api.serializers import (
    AbrirOrdemServicoInputSerializer,
    AbrirOrdemServicoOutputSerializer,
    AtualizarStatusNotificacaoInputSerializer,
    AtualizarStatusNotificacaoOutputSerializer,
    ConsultarStatusOrdemServicoOutputSerializer,
    FilaOrdemServicoItemOutputSerializer,
    ProcessarRespostaOrcamentoInputSerializer,
    ProcessarRespostaOrcamentoOutputSerializer,
    SimulacaoOrcamentoInputSerializer,
    montar_consultar_status_dto,
    montar_listar_fila_dto,
)


ERRO_DOMINIO_EXAMPLE = {
    "erro": True,
    "status_code": 400,
    "mensagem": "Mensagem de erro de dominio.",
}

def handle_domain_error(exc: DomainError) -> Response:
    """Converte erro de dominio em resposta HTTP da interface API."""
    return response_from_domain_error(exc)


def _usuario_contexto(request):
    user = request.user
    usuario_autenticado = bool(user and user.is_authenticated)
    return {
        "usuario_id": user.id if usuario_autenticado else None,
        "usuario_is_staff": bool(
            usuario_autenticado and (user.is_staff or user.is_superuser)
        ),
    }


class AbrirOrdemServicoAPIView(APIView):
    """Endpoint para abertura completa de ordem de servico."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Fase 2 - Ordens de Servico"],
        summary="Abertura completa de OS",
        description=(
            "Cria ou reutiliza cliente e veiculo, adiciona servicos e pecas, "
            "reserva estoque pela regra atual do model ItemPecaOS e retorna a "
            "ordem de servico criada com status RECEBIDA. O endpoint respeita "
            "isolamento por usuario via JWT."
        ),
        request=AbrirOrdemServicoInputSerializer,
        responses={
            201: AbrirOrdemServicoOutputSerializer,
            400: OpenApiResponse(description="Erro de validacao ou regra de negocio."),
        },
        examples=[
            OpenApiExample(
                "Payload de abertura",
                value={
                    "cliente": {
                        "nome": "Helio Teste",
                        "documento": "529.982.247-25",
                        "email": "helio@example.com",
                        "telefone": "11999999999",
                    },
                    "veiculo": {
                        "placa": "abc1d23",
                        "marca": "Volkswagen",
                        "modelo": "Golf",
                        "ano": 2024,
                    },
                    "servicos": [1, 2],
                    "pecas": [{"peca_id": 1, "quantidade": 2}],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Erro de dominio",
                value=ERRO_DOMINIO_EXAMPLE,
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def post(self, request):
        """Recebe dados de abertura, executa o use case e retorna a OS criada."""
        serializer = AbrirOrdemServicoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        input_dto = serializer.to_dto(**_usuario_contexto(request))
        use_case = build_abrir_ordem_servico_use_case()
        try:
            output_dto = use_case.execute(input_dto)
        except DomainError as exc:
            return handle_domain_error(exc)

        output_serializer = AbrirOrdemServicoOutputSerializer(output_dto)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class ConsultarStatusOrdemServicoAPIView(APIView):
    """Endpoint para consulta de status de ordem de servico."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Fase 2 - Ordens de Servico"],
        summary="Consulta de status da OS",
        description=(
            "Retorna o status atual, descricao, datas principais e valor total "
            "da ordem de servico. Usuarios comuns acessam apenas OS criadas por "
            "eles; staff e superuser podem consultar todas."
        ),
        parameters=[
            OpenApiParameter(
                name="ordem_servico_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="Identificador da ordem de servico.",
            ),
        ],
        responses={
            200: ConsultarStatusOrdemServicoOutputSerializer,
            404: OpenApiResponse(description="Ordem de servico nao encontrada ou inacessivel."),
        },
        examples=[
            OpenApiExample(
                "OS nao encontrada",
                value={
                    "erro": True,
                    "status_code": 404,
                    "mensagem": "Ordem de servico nao encontrada.",
                },
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    def get(self, request, ordem_servico_id: int):
        """Executa o use case de consulta e retorna o status da OS."""
        use_case = build_consultar_status_ordem_servico_use_case()
        input_dto = montar_consultar_status_dto(
            ordem_servico_id,
            **_usuario_contexto(request),
        )
        try:
            output_dto = use_case.execute(input_dto)
        except DomainError as exc:
            return handle_domain_error(exc)
        output_serializer = ConsultarStatusOrdemServicoOutputSerializer(output_dto)
        return Response(output_serializer.data)


class ListarFilaOrdensServicoAPIView(APIView):
    """Endpoint para listagem da fila operacional de ordens de servico."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Fase 2 - Ordens de Servico"],
        summary="Fila operacional de OS",
        description=(
            "Lista a fila operacional excluindo FINALIZADA, ENTREGUE e "
            "CANCELADA. A ordenacao e EXECUCAO, AGUARDANDO, DIAGNOSTICO, "
            "RECEBIDA e, dentro do mesmo status, OS mais antigas primeiro. "
            "O resultado respeita isolamento por usuario."
        ),
        responses={200: FilaOrdemServicoItemOutputSerializer(many=True)},
    )
    def get(self, request):
        """Executa o use case de fila e retorna as ordens operacionais."""
        use_case = build_listar_fila_ordens_servico_use_case()
        input_dto = montar_listar_fila_dto(**_usuario_contexto(request))
        try:
            output_dtos = use_case.execute(input_dto)
        except DomainError as exc:
            return handle_domain_error(exc)
        output_serializer = FilaOrdemServicoItemOutputSerializer(
            output_dtos,
            many=True,
        )
        return Response(output_serializer.data)


class ProcessarRespostaOrcamentoAPIView(APIView):
    """Endpoint para receber decisao externa de orcamento."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Fase 2 - Notificacoes"],
        summary="Notificacao de aprovacao/recusa de orcamento",
        description=(
            "Simula o recebimento autenticado de uma decisao externa de "
            "orcamento. APROVADO move AGUARDANDO para EXECUCAO; RECUSADO move "
            "AGUARDANDO para DIAGNOSTICO. O token do corpo e apenas metadado "
            "nesta fase; o endpoint segue protegido por JWT."
        ),
        request=ProcessarRespostaOrcamentoInputSerializer,
        responses={
            200: ProcessarRespostaOrcamentoOutputSerializer,
            400: OpenApiResponse(description="Decisao invalida ou OS fora de AGUARDANDO."),
            404: OpenApiResponse(description="Ordem de servico nao encontrada ou inacessivel."),
        },
        examples=[
            OpenApiExample(
                "Aprovar orcamento",
                value={
                    "ordem_servico_id": 8,
                    "decisao": "APROVADO",
                    "origem": "email",
                    "token": "simulado-opcional",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Recusar orcamento",
                value={
                    "ordem_servico_id": 8,
                    "decisao": "RECUSADO",
                    "origem": "email",
                    "motivo": "Cliente solicitou novo diagnostico.",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        """Valida a notificacao externa e executa o processamento do orcamento."""
        serializer = ProcessarRespostaOrcamentoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        use_case = build_processar_resposta_orcamento_use_case()
        try:
            output_dto = use_case.execute(
                serializer.to_dto(**_usuario_contexto(request))
            )
        except DomainError as exc:
            return handle_domain_error(exc)
        output_serializer = ProcessarRespostaOrcamentoOutputSerializer(output_dto)
        return Response(output_serializer.data)


class SimulacaoOrcamentoAPIView(APIView):
    """Endpoint para simular um sistema externo notificando decisão de orçamento."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Fase 2 - Simulação"],
        summary="Simula aprovação ou recusa de orçamento",
        description=(
            "Simula um sistema externo enviando uma decisão de orçamento "
            "para o webhook da oficina. O endpoint dispara uma chamada HTTP "
            "para /api/v1/orcamentos/notificacoes/."
        ),
        request=SimulacaoOrcamentoInputSerializer,
        responses={
            200: OpenApiResponse(
                description="Resposta retornada pelo webhook."
            ),
            400: OpenApiResponse(
                description="Payload inválido."
            ),
        },
        examples=[
            OpenApiExample(
                "Aprovar orçamento",
                value={
                    "ordem_servico_id": 8,
                    "decisao": "APROVADO",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Recusar orçamento",
                value={
                    "ordem_servico_id": 8,
                    "decisao": "RECUSADO",
                    "motivo": "Cliente não aprovou o valor.",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = SimulacaoOrcamentoInputSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        service = build_simulador_orcamento_service()

        resposta = service.enviar_decisao(
            ordem_servico_id=serializer.validated_data["ordem_servico_id"],
            decisao=serializer.validated_data["decisao"],
            motivo=serializer.validated_data.get("motivo", ""),
            authorization=request.headers.get("Authorization"),
        )

        if resposta.get("erro"):
            return Response(
                resposta,
                status=resposta.get("status_code", 400),
            )

        return Response(resposta)


class AtualizarStatusPorNotificacaoAPIView(APIView):
    """Adapter HTTP simulado para atualizacao externa de status da OS."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Fase 2 - Notificacoes"],
        summary="Atualizacao de status por notificacao",
        description=(
            "Simula uma ferramenta externa autenticada atualizando status da OS. "
            "A transicao e validada pela policy de dominio; ao finalizar, o use "
            "case tambem exige todos os servicos CONCLUIDO e todas as pecas "
            "reservadas utilizadas."
        ),
        request=AtualizarStatusNotificacaoInputSerializer,
        responses={
            200: AtualizarStatusNotificacaoOutputSerializer,
            400: OpenApiResponse(description="Transicao invalida ou regra de finalizacao violada."),
            404: OpenApiResponse(description="Ordem de servico nao encontrada ou inacessivel."),
        },
        examples=[
            OpenApiExample(
                "Atualizar status",
                value={
                    "ordem_servico_id": 8,
                    "novo_status": "DIAGNOSTICO",
                    "origem": "painel-externo",
                    "observacao": "Atualizacao simulada da Fase 2.",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Erro de finalizacao",
                value={
                    "erro": True,
                    "status_code": 400,
                    "mensagem": "Nao e possivel finalizar a OS: existem servicos nao concluidos.",
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def post(self, request):
        """Recebe uma notificacao simulada e executa o use case de status."""
        serializer = AtualizarStatusNotificacaoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        use_case = build_atualizar_status_por_notificacao_use_case()
        try:
            output_dto = use_case.execute(
                serializer.to_dto(**_usuario_contexto(request))
            )
        except DomainError as exc:
            return handle_domain_error(exc)
        output_serializer = AtualizarStatusNotificacaoOutputSerializer(output_dto)
        return Response(output_serializer.data)
