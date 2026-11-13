# Una sola imagen para todos los servicios del proyecto: cada servicio de
# docker-compose.yml arranca esta imagen con un comando distinto.

# --- base: Python + dependencias + codigo ---
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=300 \
    PATH="/opt/venv/bin:$PATH" \
    FASTEMBED_CACHE_PATH=/opt/models \
    EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

RUN pip install --no-cache-dir uv

WORKDIR /app

# UV_HTTP_TIMEOUT (arriba): con una conexion lenta, el limite por defecto de
# 30 s corta la descarga de los paquetes grandes y la construccion falla.
# Primero solo los archivos de dependencias: mientras no cambien, Docker
# reutiliza esta capa y no reinstala nada aunque cambie el codigo.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Descarga el modelo de embeddings (220 MB) dentro de la imagen. Va antes de
# copiar el codigo para que solo se descargue una vez, y asi el contenedor
# no necesita internet para indexar ni para buscar.
RUN python -c "import os; from fastembed import TextEmbedding; TextEmbedding(os.environ['EMBEDDING_MODEL'])"

COPY . .

# Usuario sin privilegios. Es dueno de /data (datos generados) y de /app
# (Chainlit escribe ahi su configuracion al arrancar).
RUN useradd --create-home appuser \
    && mkdir /data \
    && chown -R appuser:appuser /data /opt/models /app

# --- test: anade pytest y lanza los tests ---
FROM base AS test
RUN uv sync --frozen
USER appuser
CMD ["pytest", "-p", "no:cacheprovider"]

# --- runtime: la imagen que usan los servicios ---
FROM base AS runtime
USER appuser
