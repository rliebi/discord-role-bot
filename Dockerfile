# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_PATH=/data

# Minimal runtime tools only
RUN apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy source
COPY src/ /app/src/

# Add executable shim
RUN printf '#!/bin/sh\nexec python -m src.bot\n' > /app/main && chmod +x /app/main

# Healthcheck: cheap and robust (is PID 1 alive?)
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD sh -c "kill -0 1 || exit 1"

# Run as root (no chown on volumes; avoids swarm volume permission issues)
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/main"]
