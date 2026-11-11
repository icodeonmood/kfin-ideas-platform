# The isolated speech service for voice notes (DEC-096, BLD-C015). It holds only the speech engine and one Python
# file: no worker code, no secrets. Compose runs it as uid 10002 with a read-only root filesystem, a tmpfs /tmp,
# no capabilities and an internal network the worker alone shares. Model files are mounted read-only at /models.
FROM python:3.12-slim
LABEL org.kfin.project="kfin-ideas"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# WITH_ENGINE=0 builds a fake-only image for contract tests; production images keep the default.
ARG WITH_ENGINE=1
ARG FASTER_WHISPER=1.1.1
RUN if [ "$WITH_ENGINE" = "1" ]; then pip install --no-cache-dir "faster-whisper==${FASTER_WHISPER}"; fi \
    && useradd --uid 10002 --no-create-home --shell /usr/sbin/nologin speech

COPY services/worker/speech_service/service.py /app/service.py
USER 10002:10002
EXPOSE 8300
# -E: ignore PYTHON* variables; -s: no user site packages.
ENTRYPOINT ["python", "-E", "-s", "/app/service.py", "serve"]
