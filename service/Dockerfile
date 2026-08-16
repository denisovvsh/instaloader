FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY setup.py README.rst README.md ./
COPY instaloader ./instaloader
COPY service ./service

RUN pip install --no-cache-dir . \
    && pip install --no-cache-dir 'browser_cookie3>=0.19.1'

ENV PYTHONUNBUFFERED=1
ENV INSTALOADER_DATA=/data
ENV INSTALOADER_PORT=11236

EXPOSE 11236

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:11236/health || exit 1

CMD ["python", "-u", "service/api.py"]
