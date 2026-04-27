from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings


def _formatar_erros(data):
    """
    Converte os dados de erro do DRF em um formato estruturado e legível.

    Casos tratados:
      - String simples:  "Não autenticado."  →  mantém como string
      - Lista de strings: ["campo obrigatório"]  →  junta em string
      - Dict de campos:  {"nome": ["obrigatório"], "email": ["inválido"]}
                         →  {"nome": "obrigatório", "email": "inválido"}
      - Dict aninhado (ex.: serializers nested):  flattened recursivamente
    """
    if isinstance(data, str):
        return data

    if isinstance(data, list):
        # Lista de mensagens de erro (ex.: erros de campo único)
        return " | ".join(str(item) for item in data)

    if isinstance(data, dict):
        # Erros por campo — retorna dict estruturado
        erros_por_campo = {}
        for campo, mensagens in data.items():
            if campo == 'detail':
                # Campo especial do DRF (ex.: 401, 403, 404)
                return _formatar_erros(mensagens)
            if isinstance(mensagens, list):
                erros_por_campo[campo] = " | ".join(str(m) for m in mensagens)
            elif isinstance(mensagens, dict):
                erros_por_campo[campo] = _formatar_erros(mensagens)
            else:
                erros_por_campo[campo] = str(mensagens)
        return erros_por_campo

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
            # Erros de validação por campo → retorna em 'campos'
            body['mensagem'] = 'Erro de validação. Verifique os campos informados.'
            body['campos'] = erros_formatados
        else:
            # Erro geral (auth, permissão, not found etc.) → retorna em 'mensagem'
            body['mensagem'] = erros_formatados

        response.data = body

    else:
        # Erros inesperados (exceções não tratadas pelo DRF)
        body = {
            'erro': True,
            'status_code': 500,
            'mensagem': 'Erro interno no servidor da oficina. Contate o suporte.',
        }
        if settings.DEBUG:
            body['detalhes'] = str(exc)

        return Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response