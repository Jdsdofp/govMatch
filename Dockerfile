FROM python:3.13-slim

# Dependências de sistema para Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Chromium e dependências
    chromium \
    chromium-driver \
    # Libs gráficas exigidas pelo Chromium headless
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    fonts-liberation \
    # Tesseract OCR (usado pelo pytesseract)
    tesseract-ocr \
    tesseract-ocr-por \
    # Utilitários
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependências Python antes de copiar o código (melhor cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar Chromium via Playwright (usa o binário do sistema quando disponível)
ENV PLAYWRIGHT_BROWSERS_PATH=/usr/lib/chromium
RUN playwright install chromium --with-deps || true

# Copiar código
COPY . .

# Criar diretório de cache e tmp
RUN mkdir -p cache tmp/pdfs

# Variáveis de ambiente padrão (sobrescritas pela plataforma)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO \
    PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
