# Development Guide

This guide is for contributors looking to improve **fsgc**, add new signatures, or optimize the MCTS engine.

---

## 🛠 Project Structure

*   `src/fsgc/`: Core application logic.
    *   `scanner.py`: The stochastic MCTS engine.
    *   `engine.py`: Heuristic scoring and signature matching.
    *   `aggregator.py`: Grouping and summarizing the tree for the UI.
    *   `trail.py`: GCTrail binary schema and hashing logic.
    *   `ui/`: TUI components and formatters using `rich`.
*   `tests/`: Comprehensive test suite using `pytest`.
*   `plans/`: Execution plans for various features and refactors.

---

## 🏗 Development Workflow

We follow a strict **Research -> Strategy -> Execution** lifecycle for all changes.

### 🔄 The TCR Protocol
We encourage a **Test-Commit-Revert** mindset:
1.  **Write a test:** Reproduce a bug or define a new feature's behavior.
2.  **Implementation:** Make the minimal changes necessary to pass the test.
3.  **Validation:** Run `make all` to ensure all checks pass.

### 📜 Available Targets

The project includes a `makefile` for common development tasks:

| Command | Description |
| :--- | :--- |
| `make lint` | Run `ruff` linting and formatting checks. |
| `make format`| Automatically fix code style and formatting issues. |
| `make test` | Run the full `pytest` suite. |
| `make check` | Perform `mypy` static type analysis (optional). |
| `make all` | Run all linting, formatting, and tests. |

---

## 🧪 Testing Standards

*   **Async Testing:** Use `pytest-asyncio` for tests involving the `Scanner` or other asynchronous components.
*   **Mocking:** Use `unittest.mock` to simulate filesystem structures without writing to disk.
*   **Coverage:** Aim for high coverage of the core logic in `scanner.py`, `engine.py`, and `trail.py`.

Example of an async test pattern:
```python
@pytest.mark.asyncio
async def test_scanner_traversal(tmp_path):
    # Setup mock structure
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "file.txt").write_text("hello")

    scanner = Scanner(tmp_path)
    async for snapshot in scanner.scan():
        # Assertions on the snapshot
        pass
```

---

## 📏 Coding Standards

*   **Type Hinting:** All new code must be fully type-hinted and pass `mypy`.
*   **Docstrings:** Use PEP 257 docstrings for all public classes and functions.
*   **Formatting:** We use `ruff` as our primary linter and formatter. Ensure your editor is configured to use the settings in `pyproject.toml`.

---

## ⚓ The Hook System

**fsgc** uses a robust hook system (`.gemini/hooks/`) that synchronizes the development agent with your project state. These hooks automate tasks like:
*   Updating the development journal (`journal/`).
*   Running `make` targets after significant changes.
*   Updating `TASKS.md` status.
