# Worker image: API, repo writer, indexer and job runner. Build context is the repo root.
FROM python:3.12-slim
LABEL org.kfin.project="kfin-ideas"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_HTTP_TIMEOUT=600 \
    PATH=/opt/venv/bin:$PATH

# Tesseract (English and Hindi) reads images and scanned PDF pages for the week-3 file checks (§4.2, D3).
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir uv==0.9.27

WORKDIR /app
COPY services/worker/pyproject.toml services/worker/uv.lock ./
# UV_HTTP_TIMEOUT above: en-core-web-sm comes from a GitHub release (12.8 MB) that can take a minute or more to
# download, past uv's 30-second default; on 18 Nov it timed out four builds running in a row.
RUN uv sync --frozen --no-dev --no-install-project
# UAT and prod images: `--build-arg WITH_BGE=1` adds sentence-transformers for BGE-M3 (BLD-080); the model files
# are mounted at EMBEDDINGS_MODEL_PATH, never baked in or downloaded at run time.
ARG WITH_BGE=0
RUN if [ "$WITH_BGE" = "1" ]; then uv pip install --python /opt/venv/bin/python "sentence-transformers>=3,<6"; fi
# Voice notes (DEC-096): `--build-arg WITH_SPEECH=1` adds faster-whisper for SPEECH_MODE=local; the model files are
# mounted at SPEECH_MODEL_PATH, never baked in or downloaded at run time. About 2–3 GB more memory on the host.
ARG WITH_SPEECH=0
RUN if [ "$WITH_SPEECH" = "1" ]; then uv pip install --python /opt/venv/bin/python "faster-whisper>=1.1,<2"; fi

COPY services/worker/ ./
COPY agents/ ./agents/
RUN useradd --create-home --uid 10001 worker && chown -R worker /app
USER worker

EXPOSE 8000
CMD ["python", "-m", "service"]
