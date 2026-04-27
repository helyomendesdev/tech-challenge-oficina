from rest_framework.throttling import AnonRateThrottle


class ConsultaClienteThrottle(AnonRateThrottle):
    """
    Throttle dedicado ao endpoint público /consulta-cliente.

    Limite configurável via settings:
        'DEFAULT_THROTTLE_RATES': {
            'consulta_cliente': '30/hour',
        }

    Identificação do cliente por IP (comportamento padrão de AnonRateThrottle).
    """
    scope = 'consulta_cliente'
