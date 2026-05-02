# Imagem base oficial do Python
FROM python:3.11-slim

# Impede que o Python gere arquivos .pyc e permite log em tempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Diretório de trabalho dentro do container
WORKDIR /app

# Instala dependências do sistema e cria usuário não-root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash appuser

# Copia e instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Ajusta permissões para o usuário não-root
RUN chown -R appuser:appuser /app

# Healthcheck da aplicação
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Executa como usuário não-root
USER appuser

# Comando de produção com gunicorn
CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
