import logging

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from atendimento.domain.exceptions import (
    DomainError,
    EstoqueInsuficienteError,
    OrcamentoNaoPodeSerProcessadoError,
    OrdemServicoNaoEncontradaError,
    RegraFinalizacaoOrdemServicoError,
    TransicaoStatusInvalidaError,
)


logger = logging.getLogger(__name__)
MENSAGEM_ERRO_VALIDACAO = 'Erro de validação. Verifique os campos informados.'

DOMAIN_ERROR_STATUS_MAP = {
    OrdemServicoNaoEncontradaError: status.HTTP_404_NOT_FOUND,
    TransicaoStatusInvalidaError: status.HTTP_400_BAD_REQUEST,
    EstoqueInsuficienteError: status.HTTP_400_BAD_REQUEST,
    RegraFinalizacaoOrdemServicoError: status.HTTP_400_BAD_REQUEST,
    OrcamentoNaoPodeSerProcessadoError: status.HTTP_400_BAD_REQUEST,
    DomainError: status.HTTP_400_BAD_REQUEST,
}


def resposta_erro(mensagem, status_code=status.HTTP_400_BAD_REQUEST, campos=None):
    """Monta o formato padrao de erro usado pela API."""
    body = {
        'erro': True,
        'status_code': status_code,
        'mensagem': mensagem,
    }
    if campos is not None:
        body['campos'] = campos
    return body


def status_code_domain_error(exc):
    """Mapeia exceptions de dominio para HTTP sem depender de DRF nas camadas."""
    return next(
        (
            http_status
            for error_class, http_status in DOMAIN_ERROR_STATUS_MAP.items()
            if isinstance(exc, error_class)
        ),
        status.HTTP_400_BAD_REQUEST,
    )


def response_from_domain_error(exc):
    """Converte DomainError em Response padronizada."""
    status_code = status_code_domain_error(exc)
    return Response(
        resposta_erro(str(exc), status_code),
        status=status_code,
    )


def _formatar_django_validation_error(exc):
    """Converte ValidationError do Django em mensagem/campos de erro."""
    if hasattr(exc, 'message_dict'):
        return (
            MENSAGEM_ERRO_VALIDACAO,
            _formatar_dict(exc.message_dict),
        )
    if hasattr(exc, 'messages'):
        return _formatar_lista(exc.messages), None
    return str(exc), None


def _formatar_string(data):
    """Mantém strings de erro como estão."""
    return data


def _formatar_lista(data):
    """Junta lista de mensagens em uma única string."""
    return " | ".join(str(item) for item in data)


def _formatar_campo(mensagens):
    """Formata o valor de um campo de erro (list, dict ou escalar)."""
    if isinstance(mensagens, list):
        return " | ".join(str(m) for m in mensagens)
    if isinstance(mensagens, dict):
        return _formatar_dict(mensagens)
    return str(mensagens)


def _formatar_dict(data):
    """
    Converte dict de erros do DRF em formato estruturado.

    Trata o campo especial 'detail' (401, 403, 404) recursivamente.
    """
    erros_por_campo = {}
    for campo, mensagens in data.items():
        if campo == 'detail':
            return _formatar_erros(mensagens)
        erros_por_campo[campo] = _formatar_campo(mensagens)
    return erros_por_campo


def _formatar_erros(data):
    """
    Dispatcher que converte qualquer tipo de dado de erro em formato legível.

    Casos tratados:
      - String simples:  mantém como string
      - Lista de strings: junta em string
      - Dict de campos: retorna dict estruturado
      - Dict aninhado (nested serializers): flattened recursivamente
    """
    if isinstance(data, str):
        return _formatar_string(data)
    if isinstance(data, list):
        return _formatar_lista(data)
    if isinstance(data, dict):
        return _formatar_dict(data)
    return str(data)


def custom_exception_handler(exc, context):
    """
    Handler global de erros para a API da Oficina.

    Padroniza todas as respostas de erro no formato:
      {
        "erro": true,
        "status_code": 4xx,
        "mensagem": "Descrição geral",   ← erros simples (401, 403, 404)
        "campos": { ... }                ← erros por campo (400 de validação)
      }
    """
    if isinstance(exc, DomainError):
        return response_from_domain_error(exc)

    if isinstance(exc, DjangoValidationError):
        mensagem, campos = _formatar_django_validation_error(exc)
        return Response(
            resposta_erro(mensagem, status.HTTP_400_BAD_REQUEST, campos),
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)

    if response is not None:
        erros_formatados = _formatar_erros(response.data)

        if isinstance(erros_formatados, dict):
            body = resposta_erro(
                MENSAGEM_ERRO_VALIDACAO,
                response.status_code,
                erros_formatados,
            )
        else:
            body = resposta_erro(erros_formatados, response.status_code)

        response.data = body

    else:
        logger.exception("Erro nao tratado na API")
        body = resposta_erro(
            'Erro interno no servidor da oficina. Contate o suporte.',
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        if settings.DEBUG:
            body['detalhes'] = str(exc)

        return Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response
