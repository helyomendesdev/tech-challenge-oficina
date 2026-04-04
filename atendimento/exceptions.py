from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

def custom_exception_handler(exc, context):
    # Chama o manipulador padrão do DRF primeiro
    response = exception_handler(exc, context)

    if response is not None:
        # Personaliza o formato do erro para o padrão da sua Oficina
        response.data = {
            'erro': True,
            'mensagem': response.data.get('detail', 'Ocorreu um erro na solicitação.'),
            'status_code': response.status_code
        }
    else:
        # Erros inesperados (Ex: Erro de código puro)
        return Response({
            'erro': True,
            'mensagem': 'Erro interno no servidor da oficina. Contate o suporte.',
            'detalhes': str(exc)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response