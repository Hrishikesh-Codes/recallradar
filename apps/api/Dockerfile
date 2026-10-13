# API image. Built from the repo root:  docker build -f apps/api/Dockerfile .
# Also the image Hugging Face Spaces runs, which requires uid 1000 and (by default) port 7860.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PORT=7860

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --chown=app:app . .
RUN uv sync --frozen --no-dev --package recallradar-api && chown -R app:app /app/.venv

USER app
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn recallradar_api.main:create_app --factory --host 0.0.0.0 --port ${PORT}"]
