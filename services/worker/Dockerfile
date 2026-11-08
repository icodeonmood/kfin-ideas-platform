# Worker image: API, repo writer, indexer and job runner. Build context is the repo root.
FROM python:3.12-slim

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

COPY services/worker/ ./
RUN useradd --create-home --uid 10001 worker && chown -R worker /app
USER worker

EXPOSE 8000
CMD ["python", "-m", "service"]
