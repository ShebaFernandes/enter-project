# syntax=docker/dockerfile:1.7
FROM python:3.13.7-slim@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/enter-venv \
    PATH=/opt/enter-venv/bin:$PATH
RUN groupadd --gid 10001 enter && useradd --uid 10001 --gid enter --create-home enter
WORKDIR /workspace/app
COPY --from=ghcr.io/astral-sh/uv:0.8.22@sha256:9874eb7afe5ca16c363fe80b294fe700e460df29a55532bbfea234a0f12eddb1 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev || uv sync --no-dev
COPY docker/entrypoint.sh /usr/local/bin/enter-entrypoint
COPY --chown=enter:enter . .
RUN chmod 0555 /usr/local/bin/enter-entrypoint
USER enter
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/enter-entrypoint"]
CMD ["web"]
