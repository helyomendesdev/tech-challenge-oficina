from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings


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
    response = exception_handler(exc, context)

    if response is not None:
        erros_formatados = _formatar_erros(response.data)

        body = {
            'erro': True,
            'status_code': response.status_code,
        }

        if isinstance(erros_formatados, dict):
            body['mensagem'] = 'Erro de validação. Verifique os campos informados.'
            body['campos'] = erros_formatados
        else:
            body['mensagem'] = erros_formatados

        response.data = body

    else:
        body = {
            'erro': True,
            'status_code': 500,
            'mensagem': 'Erro interno no servidor da oficina. Contate o suporte.',
        }
        if settings.DEBUG:
            body['detalhes'] = str(exc)

        return Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response
