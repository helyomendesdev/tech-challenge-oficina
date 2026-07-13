"""
Django settings for app project.

Gerado por 'django-admin startproject' com Django 5.1.
Documentação: https://docs.djangoproject.com/en/5.1/topics/settings/
"""

import os
from pathlib import Path
from datetime import timedelta
from decouple import config, Csv  # C4: gestão segura de env vars

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Segurança
# ---------------------------------------------------------------------------

# C4 CORRIGIDO: sem fallback hardcoded — lança erro se a variável não existir
SECRET_KEY = config('DJANGO_SECRET_KEY')

DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# ---------------------------------------------------------------------------
# Aplicações instaladas
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',             # CORS
    'csp',                     # Content Security Policy
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'django_filters',           # Filtros avançados
    'atendimento',
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'csp.middleware.CSPMiddleware',           # Content Security Policy
    'corsheaders.middleware.CorsMiddleware',  # CORS — deve vir antes de CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'

# ---------------------------------------------------------------------------
# Banco de Dados
# ---------------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB', default='oficina_db'),
        'USER': config('POSTGRES_USER', default='admin'),
        'PASSWORD': config('POSTGRES_PASSWORD'),
        'HOST': config('DB_HOST', default='db'),
        'PORT': '5432',
    }
}

# ---------------------------------------------------------------------------
# Integrações externas
# ---------------------------------------------------------------------------

WEBHOOK_ORCAMENTO_URL = config(
    "WEBHOOK_ORCAMENTO_URL",
    default="http://localhost:8000/api/v1/orcamentos/notificacoes/",
)

# ---------------------------------------------------------------------------
# Validação de senhas
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internacionalização
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Arquivos estáticos
# ---------------------------------------------------------------------------

STATIC_URL = '/static/'
STATIC_ROOT = config(
    'STATIC_ROOT',
    default=str(BASE_DIR / 'staticfiles'),
)  # M11: necessário para collectstatic em produção

# ---------------------------------------------------------------------------
# Auto field padrão
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'atendimento.exceptions.custom_exception_handler',
    # Paginação global — evita retornar listas ilimitadas
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # Filtros — habilita ?status=RECEBIDA, ?data_abertura_after=2026-01-01, etc.
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    # Throttling global
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/hour',          # Usuários não autenticados
        'user': '600/hour',         # Usuários autenticados
        'consulta_cliente': '30/hour',  # Endpoint público de consulta
    },
}

# ---------------------------------------------------------------------------
# JWT — lifetimes explícitos
# ---------------------------------------------------------------------------

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# ---------------------------------------------------------------------------
# Swagger / OpenAPI
# ---------------------------------------------------------------------------

SPECTACULAR_SETTINGS = {
    'TITLE': 'API Oficina Mecânica — Tech Challenge',
    'DESCRIPTION': 'Sistema de gestão de Ordens de Serviço e estoque.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'ENUM_NAME_OVERRIDES': {
        'StatusOrdemServicoEnum': 'atendimento.models.OrdemServico.STATUS_CHOICES',
        'StatusItemServicoEnum': 'atendimento.models.ItemServicoOS.STATUS_CHOICES',
    },
}

# ---------------------------------------------------------------------------
# CORS — M12
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://localhost:5173',
    cast=Csv(),
)

# ---------------------------------------------------------------------------
# Content Security Policy (CSP) — OWASP A05
# ---------------------------------------------------------------------------

# Domínios CDN usados por drf-spectacular (swagger-ui / redoc)
_CSP_CDNS = (
    'https://unpkg.com',
    'https://cdn.jsdelivr.net',
    'https://fonts.googleapis.com',
    'https://fonts.gstatic.com',
)

_CSP_SELF = "'self'"
CSP_DEFAULT_SRC = (_CSP_SELF,)
CSP_SCRIPT_SRC = (_CSP_SELF, "'unsafe-inline'") + _CSP_CDNS  # swagger-ui usa script inline na inicialização
CSP_STYLE_SRC = (_CSP_SELF, "'unsafe-inline'") + _CSP_CDNS  # swagger-ui precisa de inline styles
CSP_IMG_SRC = (_CSP_SELF, "data:", "blob:")
CSP_FONT_SRC = (_CSP_SELF,) + _CSP_CDNS
CSP_CONNECT_SRC = (_CSP_SELF,)
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_BASE_URI = (_CSP_SELF,)
CSP_FORM_ACTION = (_CSP_SELF,)

# ---------------------------------------------------------------------------
# Headers de segurança HTTP (ativos apenas em produção)
# ---------------------------------------------------------------------------

if not DEBUG:
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'

# ---------------------------------------------------------------------------
# Logging — L4: caminho absoluto para funcionar dentro do Docker
# ---------------------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.environ.get('DJANGO_LOG_FILE', str(BASE_DIR / 'oficina_atividades.log')),
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'atendimento': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
