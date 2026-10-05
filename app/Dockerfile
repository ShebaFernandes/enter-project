# syntax=docker/dockerfile:1.7
FROM node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c AS frontend-build
WORKDIR /workspace/app
COPY package.json package-lock.json ./
RUN npm ci
COPY frontend ./frontend
COPY tests/browser/fixtures/fm2-showcase.tsx ./tests/browser/fixtures/fm2-showcase.tsx
COPY tsconfig.json vite.config.ts ./
RUN npm run build:all

FROM python:3.13.7-slim@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/enter-venv \
    PATH=/opt/enter-venv/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr antiword && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 10001 enter && useradd --uid 10001 --gid enter --create-home enter
WORKDIR /workspace/app
COPY --from=ghcr.io/astral-sh/uv:0.8.22@sha256:9874eb7afe5ca16c363fe80b294fe700e460df29a55532bbfea234a0f12eddb1 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev || uv sync --no-dev
COPY docker/entrypoint.sh /usr/local/bin/enter-entrypoint
COPY --chown=enter:enter . .
COPY --from=frontend-build --chown=enter:enter /workspace/app/static/dist ./static/dist
RUN chmod 0555 /usr/local/bin/enter-entrypoint
USER enter
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/enter-entrypoint"]
CMD ["web"]
