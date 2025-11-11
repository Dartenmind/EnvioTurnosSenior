# Dockerfile para EnvioTurnosSenior - Deploy no Coolify
# Aplicação Flask com WebSocket para envio de escalas à API Senior

FROM python:3.11-slim

# Metadados da imagem
LABEL maintainer="EnvioTurnosSenior"
LABEL description="Sistema automatizado de envio de escalas de turnos para Senior API"

# Define diretório de trabalho
WORKDIR /app

# Variáveis de ambiente para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instala dependências do sistema (se necessário)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia arquivo de dependências
COPY requirements.txt .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY app.py .
COPY envio_escala_api_corrigido.py .
COPY data_convert.py .
COPY test_integracao.py .

# Copia módulos do diretório src
COPY src/ ./src/

# Copia templates e arquivos estáticos
COPY templates/ ./templates/
COPY static/ ./static/

# Copia arquivo de mapeamento de horários (dado estático crítico)
COPY horarios.csv .

# Copia arquivo exemplo (opcional)
COPY escala_colaboradores.csv .

# Cria diretórios para dados dinâmicos
RUN mkdir -p /app/input_data /app/output_data /app/temp && \
    chmod 755 /app/input_data /app/output_data /app/temp

# Cria usuário não-root para segurança
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Muda para usuário não-root
USER appuser

# Expõe porta 3000 (padrão para Coolify)
EXPOSE 3000

# Health check para monitoramento
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:3000/', timeout=5)" || exit 1

# Comando para iniciar a aplicação em produção com Gunicorn
# --worker-class eventlet: Suporte a WebSocket/Socket.IO
# -w 1: 1 worker (eventlet é single-threaded mas async)
# --bind 0.0.0.0:3000: Escuta em todas as interfaces na porta 3000
# --log-level info: Logging adequado para produção
# --access-logfile -: Logs de acesso no stdout (Docker-friendly)
# --error-logfile -: Logs de erro no stdout (Docker-friendly)
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:3000", "--log-level", "info", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
