# Scaffolding Plan: `gc` (Garbage Collector)

This plan outlines the steps to initialize the `gc` project using modern Python tooling (`uv`, `ruff`, `pytest`).

## Phase 1: Environment & Dependency Initialization

1.  **Project Initialization:**
    - Run `uv init --app --package gc` to create a new Python project.
2.  **Add Core Dependencies:**
    - `uv add rich pyyaml typer sqlitedict`
3.  **Add Development & Testing Dependencies:**
    - `uv add --dev ruff pytest pytest-cov mypy`

## Phase 2: Directory Structure & Boilerplate

Create the following file structure to reflect the design's Pipe-and-Filter architecture:

- `src/gc/`
  - `__init__.py`
  - `__main__.py` (CLI entry point)
  - `scanner.py` (Breadth-First Search scanning engine)
  - `engine.py` (Heuristic scoring logic)
  - `aggregator.py` (Aggregation and "Sweep" logic)
  - `ui/` (Rich-based UI components)
    - `__init__.py`
    - `formatter.py` (Formatting logic for the density map)
  - `config.py` (YAML signature loading)
- `config/`
  - `signatures.yaml` (Default "Garbage" patterns)
- `tests/`
  - `conftest.py`
  - `test_scanner.py`
  - `test_engine.py`

## Phase 3: Build & Tooling Configuration

1.  **Update `pyproject.toml`:**
    - Configure `ruff` for linting and formatting.
    - Configure `mypy` for static type checking.
    - Set up the `gc` script entry point.
2.  **Create/Update `makefile`:**
    - `make lint`: Run `ruff check` and `ruff format --check`.
    - `make test`: Run `pytest` with coverage.
    - `make check`: Run `mypy` for type safety.
    - `make all` (Default): `lint test check`.

## Phase 4: Initial Implementation Hooks

- Scaffolding a basic BFS `os.scandir` implementation in `scanner.py`.
- Creating a sample `signatures.yaml`.
- Building a minimalist "Proposal" prompt in `ui/formatter.py` using `Rich.table`.

## Verification

- Run `make all` to ensure the project passes initial linting and an empty test suite.
