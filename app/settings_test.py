"""
Settings específicos para testes locais.

Herda tudo de app.settings e sobrescreve apenas o banco de dados
para usar SQLite em memória, eliminando a dependência do PostgreSQL
Docker durante o desenvolvimento e CI local.

Uso: pytest (configurado via pytest.ini com DJANGO_SETTINGS_MODULE=app.settings_test)
"""

from .settings import *  # noqa: F401, F403

# Banco SQLite em memória — rápido, sem dependências externas
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Desativa redirecionamento SSL nos testes
SECURE_SSL_REDIRECT = False

# Desativa coleta de estático que exigiria arquivos no disco
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
