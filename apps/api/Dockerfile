# API image. Built from the repo root:  docker build -f apps/api/Dockerfile .
# Runs as uid 1000 on port $PORT (7860 by default); deploy/oracle/compose.yaml runs it in production.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    MODEL_CACHE_DIR=/app/models \
    PORT=7860

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --chown=app:app . .
RUN uv sync --frozen --no-dev --package recallradar-api && chown -R app:app /app/.venv \
    && mkdir -p /app/models && chown app:app /app/models

USER app
# Bake the embedding model (BAAI/bge-small-en-v1.5, ~67 MB) into the image, then never reach
# Hugging Face's hub at runtime: cold starts don't download anything.
RUN python -c "from pathlib import Path; from recallradar_matching.embed import Embedder; Embedder(Path('/app/models')).warm_up()"
ENV HF_HUB_OFFLINE=1

EXPOSE 7860
# Behind a reverse proxy the client address (for rate limits) comes from X-Forwarded-For, trusted
# only from the addresses in $FORWARDED_ALLOW_IPS (uvicorn's default: 127.0.0.1 only).
CMD ["sh", "-c", "exec uvicorn recallradar_api.main:create_app --factory --host 0.0.0.0 --port ${PORT} --proxy-headers"]
