# Worker image: API, repo writer, indexer and job runner. Build context is the repo root.
FROM python:3.12-slim
LABEL org.kfin.project="kfin-ideas"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir uv==0.9.27

WORKDIR /app
COPY services/worker/pyproject.toml services/worker/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# UAT and prod images: `--build-arg WITH_BGE=1` adds sentence-transformers for BGE-M3 (BLD-080); the model files
# are mounted at EMBEDDINGS_MODEL_PATH, never baked in or downloaded at run time.
ARG WITH_BGE=0
RUN if [ "$WITH_BGE" = "1" ]; then uv pip install --python /opt/venv/bin/python "sentence-transformers>=3,<6"; fi

COPY services/worker/ ./
COPY agents/ ./agents/
RUN useradd --create-home --uid 10001 worker && chown -R worker /app
USER worker

EXPOSE 8000
CMD ["python", "-m", "service"]
