from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from atendimento.models import (
    Cliente,
    ConsumoItemServico,
    ItemPecaOS,
    ItemServicoOS,
    OrdemServico,
    Peca,
    Servico,
    Veiculo,
)


DEFAULT_PASSWORD = 'senha@123'


# Helpers compartilhados pelos testes legados e de integracao.
def create_user(username='tecnico', password=DEFAULT_PASSWORD, **kwargs):  # NOSONAR
    return User.objects.create_user(  # nosec B106,B107 # NOSONAR
        username=username,
        password=password,
        **kwargs,
    )


def create_staff_user(username='gestor', password=DEFAULT_PASSWORD, **kwargs):  # NOSONAR
    return create_user(username=username, password=password, is_staff=True, **kwargs)


def create_superuser(username='admin', password=DEFAULT_PASSWORD, **kwargs):  # NOSONAR
    return User.objects.create_superuser(  # nosec B106,B107 # NOSONAR
        username=username,
        password=password,
        **kwargs,
    )


def api_client_for_user(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def authenticate_client(client, user):
    client.force_authenticate(user=user)
    return client


def criar_usuario(username='tecnico', password=DEFAULT_PASSWORD, **kwargs):  # NOSONAR
    return create_user(username=username, password=password, **kwargs)


def create_cliente(usuario=None, **kwargs):
    defaults = {
        'nome': 'Helio Teste',
        'documento': '529.982.247-25',
        'email': 'helio@teste.com',
        'telefone': '11999999999',
    }
    defaults.update(kwargs)
    if usuario:
        defaults['created_by'] = usuario
    return Cliente.objects.create(**defaults)


def criar_cliente(usuario=None, **kwargs):
    return create_cliente(usuario=usuario, **kwargs)


def create_veiculo(cliente, usuario=None, **kwargs):
    defaults = {
        'placa': 'GTI2E26',
        'marca': 'Volkswagen',
        'modelo': 'Golf GTI',
        'ano': 2026,
    }
    defaults.update(kwargs)
    if usuario:
        defaults['created_by'] = usuario
    return Veiculo.objects.create(cliente=cliente, **defaults)


def criar_veiculo(cliente, usuario=None, **kwargs):
    return create_veiculo(cliente, usuario=usuario, **kwargs)


def create_servico(usuario=None, **kwargs):
    defaults = {'descricao': 'Troca de Oleo', 'valor_mao_de_obra': 150.00}
    defaults.update(kwargs)
    if usuario:
        defaults['created_by'] = usuario
    return Servico.objects.create(**defaults)


def criar_servico(usuario=None, **kwargs):
    return create_servico(usuario=usuario, **kwargs)


def create_peca(usuario=None, **kwargs):
    defaults = {
        'nome': 'Pastilha de Freio',
        'valor_unitario': 90.00,
        'estoque_atual': 10,
    }
    defaults.update(kwargs)
    if usuario:
        defaults['created_by'] = usuario
    return Peca.objects.create(**defaults)


def criar_peca(usuario=None, **kwargs):
    return create_peca(usuario=usuario, **kwargs)


def create_ordem_servico(cliente, veiculo, usuario=None, **kwargs):
    defaults = {'created_by': usuario}
    defaults.update(kwargs)
    return OrdemServico.objects.create(cliente=cliente, veiculo=veiculo, **defaults)


def criar_ordem_servico(cliente, veiculo, usuario=None, **kwargs):
    return create_ordem_servico(cliente, veiculo, usuario=usuario, **kwargs)


def create_item_servico_os(os, servico, usuario=None, status='PENDENTE', **kwargs):
    return ItemServicoOS.objects.create(
        ordem_servico=os,
        servico=servico,
        created_by=usuario,
        status=status,
        **kwargs,
    )


def criar_item_servico_os(os, servico, usuario=None, status='PENDENTE', **kwargs):
    return create_item_servico_os(os, servico, usuario=usuario, status=status, **kwargs)


def create_item_peca_os(os, peca, usuario=None, **kwargs):
    return ItemPecaOS.objects.create(
        os=os,
        peca=peca,
        created_by=usuario,
        **kwargs,
    )


def criar_item_peca_os(os, peca, usuario=None, **kwargs):
    return create_item_peca_os(os, peca, usuario=usuario, **kwargs)
