# ==========================================================================
# AI Video Dubbing Platform V3.0 - Production Dockerfile
# ==========================================================================

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and buffering stdout/stderr,
# which keeps container logs flowing to `docker logs` / Render logs
# in real time.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# --------------------------------------------------------------------------
# System Dependencies: FFmpeg (audio/video processing) + build tools
# --------------------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --------------------------------------------------------------------------
# Python Dependencies (copied first to maximize Docker layer caching)
# --------------------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --------------------------------------------------------------------------
# OPTIONAL: Heavy local TTS engines (Piper, XTTS) -- NOT installed by default
# --------------------------------------------------------------------------
# These pull in large native/ML dependencies (onnxruntime, PyTorch) and are
# not compatible with Render's free tier. To self-host either engine on a
# larger instance, uncomment the two lines below and provide the Piper
# binary / XTTS model + reference speaker files via env vars at runtime:
#
#   COPY requirements-optional.txt .
#   RUN pip install --no-cache-dir -r requirements-optional.txt

# --------------------------------------------------------------------------
# Application Source
# --------------------------------------------------------------------------
COPY . .

# Ensure the storage directory tree exists inside the image (also created
# at runtime by Settings.ensure_directories(), but pre-creating avoids any
# permission surprises on first boot).
RUN mkdir -p storage/uploads storage/outputs storage/audio storage/temp storage/subtitles storage/logs

# --------------------------------------------------------------------------
# Run as a non-root user (production hardening: never run network-facing
# processes as root inside a container).
# --------------------------------------------------------------------------
RUN groupadd --system dubbing && \
    useradd --system --gid dubbing --home-dir /app --no-create-home dubbing && \
    chown -R dubbing:dubbing /app

USER dubbing

# --------------------------------------------------------------------------
# Runtime Configuration
# --------------------------------------------------------------------------
ENV HOST=0.0.0.0 \
    PORT=8000 \
    ENVIRONMENT=production

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# --------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------
# Render (and most PaaS providers) inject $PORT at runtime, so the shell
# form is used to allow environment variable expansion.
CMD uvicorn app:app --host ${HOST} --port ${PORT} --workers 1
