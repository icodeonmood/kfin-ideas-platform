# The isolated speech service for voice notes (DEC-096, BLD-C015). It holds only the speech engine and one Python
# file: no worker code, no secrets. Compose runs it as uid 10002 with a read-only root filesystem, a noexec tmpfs
# /tmp, no capabilities and an internal network the worker alone shares. Model files are mounted read-only at /models.
#
# Supply chain (BLD-C032): the base image is pinned by digest (python:3.12-slim, multi-architecture index) and every
# Python package, faster-whisper and all it pulls in, by version and hash, wheels only. RUNBOOK ("The speech
# service's image") says how to refresh both.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
LABEL org.kfin.project="kfin-ideas"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# WITH_ENGINE=0 builds a fake-only image for contract tests; production images keep the default.
ARG WITH_ENGINE=1
COPY services/worker/speech_service/requirements.txt /tmp/requirements.txt
RUN if [ "$WITH_ENGINE" = "1" ]; then \
      pip install --no-cache-dir --require-hashes --only-binary=:all: --no-deps -r /tmp/requirements.txt; \
    fi \
    && rm /tmp/requirements.txt \
    && useradd --uid 10002 --no-create-home --shell /usr/sbin/nologin speech

COPY services/worker/speech_service/service.py /app/service.py
USER 10002:10002
EXPOSE 8300
# -E: ignore PYTHON* variables; -s: no user site packages.
ENTRYPOINT ["python", "-E", "-s", "/app/service.py", "serve"]
