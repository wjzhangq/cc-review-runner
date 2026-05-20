.PHONY: install test lint typecheck build smoke clean ci format

install:
	uv sync --all-extras

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff format src tests

typecheck:
	uv run mypy

build:
	uv build

smoke:
	bash scripts/smoke.sh

ci: lint typecheck test build

clean:
	rm -rf dist .pytest_cache .mypy_cache .ruff_cache
