.PHONY: bootstrap services services-down migrate fixtures dev check test test-contract test-browser test-security test-sbom test-load test-ai makemigrations

bootstrap:
	test -f .env || cp .env.example .env
	cd app && uv sync --all-groups
	cd app && npm ci
	cd app && npm run build:all

services:
	docker compose up -d postgres valkey s3-local mail resume-scanner

services-down:
	docker compose down

migrate:
	docker compose run --rm --build web python manage.py migrate

makemigrations:
	cd app && uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test

fixtures:
	docker compose run --rm web python manage.py load_synthetic_foundation

dev:
	docker compose up --build web worker

check:
	cd app && uv run ruff check .
	cd app && uv run ruff format --check .
	cd app && uv run mypy .
	cd app && npm run check

test:
	cd app && uv run pytest --cov=config --cov=modules --cov-report=term-missing

test-contract:
	cd app && uv run pytest tests/contract

test-browser:
	cd app && npm run test:browser

test-security:
	cd app && uv run bandit -q -r config modules
	cd app && uv run pip-audit

test-sbom:
	cd app && uv run pip-audit --format cyclonedx-json --output sbom.cdx.json

test-load:
	@echo "Load tests start in a later phase."

test-ai:
	@echo "AI evaluation starts in a later phase."
