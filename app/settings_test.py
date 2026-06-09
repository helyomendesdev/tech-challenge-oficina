"""
Settings específicos para testes locais.

Herdado de app.settings e sobrescreve apenas o banco de dados
para usar SQLite em memória, eliminando a dependência do PostgreSQL
Docker durante o desenvolvimento e CI local.

Uso: pytest (configurado via pytest.ini com DJANGO_SETTINGS_MODULE=app.settings_test)
"""

from .settings import *  # noqa: F401,F403  # NOSONAR

# Banco SQLite em memória — rápido, sem dependências externas
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Desativa redirecionamento SSL nos testes
SECURE_SSL_REDIRECT = False

# Permite o host padrão dos testes Django
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']

# Desativa coleta de estático que exigiria arquivos no disco
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# WhiteNoise valida STATIC_ROOT e gera warnings em testes; os endpoints testados
# nao dependem de serving de arquivos estaticos.
MIDDLEWARE = [
    middleware
    for middleware in MIDDLEWARE  # noqa: F405
    if middleware != 'whitenoise.middleware.WhiteNoiseMiddleware'
]

# Hash rapido para reduzir o custo de User.objects.create_user nos testes.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Evita validacoes de senha desnecessarias no ambiente de teste.
AUTH_PASSWORD_VALIDATORS = []

# Cache isolado em memoria para testes locais e CI.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}

# Mantem DRF/JWT herdados de settings.py, explicitando apenas que o ambiente
# de teste usa as mesmas classes e contratos da API real.
REST_FRAMEWORK = REST_FRAMEWORK.copy()  # noqa: F405
SIMPLE_JWT = SIMPLE_JWT.copy()  # noqa: F405

# Backend de email em memoria, caso algum fluxo passe a enviar notificacao real.
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Silencia logs em testes e evita criar oficina_atividades.log.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'root': {
        'handlers': ['null'],
        'level': 'CRITICAL',
    },
    'loggers': {
        'django': {
            'handlers': ['null'],
            'level': 'CRITICAL',
            'propagate': False,
        },
        'atendimento': {
            'handlers': ['null'],
            'level': 'CRITICAL',
            'propagate': False,
        },
    },
}
