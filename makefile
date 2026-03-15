.PHONY: all test lint format check

all: lint test check

test:
	@uv run pytest

lint:
	@uv run ruff check .
	@uv run ruff format --check .

format:
	@uv run ruff check --fix .
	@uv run ruff format .

check:
	@uv run mypy src/ tests/
