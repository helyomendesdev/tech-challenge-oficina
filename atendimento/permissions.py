from rest_framework.permissions import BasePermission

from atendimento.authentication import ClientPrincipal
from atendimento.models import OrdemServico, Veiculo


def is_client_principal(user):
    """Identifica o principal externo de Cliente sem depender de auth.User."""
    return isinstance(user, ClientPrincipal)


def is_authenticated_principal(user):
    return bool(user and user.is_authenticated)


class ClienteJWTViewSetPermission(BasePermission):
    """
    Permissao explicita para coexistencia entre funcionarios e Cliente JWT.

    Funcionarios autenticados mantem o comportamento legado. Cliente JWT acessa
    apenas actions declaradas em `cliente_jwt_allowed_actions` no ViewSet.
    """

    def has_permission(self, request, view):
        user = request.user
        if not is_authenticated_principal(user):
            return False
        if not is_client_principal(user):
            return True

        action = getattr(view, "action", None)
        allowed_actions = getattr(view, "cliente_jwt_allowed_actions", set())
        return action in allowed_actions

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not is_client_principal(user):
            return True
        if isinstance(obj, Veiculo):
            return obj.cliente_id == user.cliente_id
        if isinstance(obj, OrdemServico):
            return obj.cliente_id == user.cliente_id
        return False


class DenyClientPrincipalPermission(BasePermission):
    """Permite funcionarios/staff autenticados e nega Cliente JWT."""

    def has_permission(self, request, view):
        user = request.user
        return is_authenticated_principal(user) and not is_client_principal(user)


class ClienteJWTStatusPermission(BasePermission):
    """Permite consulta de status para Cliente JWT ou usuario Django."""

    def has_permission(self, request, view):
        return is_authenticated_principal(request.user)
