.PHONY: all test lint format

all: format lint test

test:
	@uv run pytest

lint:
	@uv run ruff check .
	@uv run ruff format --check .

format:
	@uv run ruff check --fix .
	@uv run ruff format .
