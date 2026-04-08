# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Talent-Audit-Env  —  Dockerfile
# Multi-stage build: keeps the final image lean (~200 MB)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── Stage 1: dependency builder ───────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools (required by some wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install into a prefix so we can copy it cleanly
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: lean runtime ─────────────────────────────
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="Talent-Audit-Env" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.description="OpenEnv-compliant HR Data Compliance environment" \
      org.opencontainers.image.licenses="MIT"

# Hugging Face Spaces requirements
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copy pre-built site-packages from builder stage (changing owner to user)
COPY --from=builder --chown=user:user /install /usr/local

# Copy application source
COPY --chown=user:user models.py   ./models.py
COPY --chown=user:user tasks.py    ./tasks.py
COPY --chown=user:user env.py      ./env.py
COPY --chown=user:user main.py     ./main.py
COPY --chown=user:user run_demo.py ./run_demo.py
COPY --chown=user:user openenv.yaml ./openenv.yaml

# Expose port (HF convention is 7860)
EXPOSE 7860

# Health-check  (requires the /health endpoint in main.py)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"

# Default: start the FastAPI server
# Override with `docker run ... python run_demo.py` for CLI demo
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]