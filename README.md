# 🤖 Garbage Collector (gc)

<div align="center">

[![Release](https://img.shields.io/badge/Release-v0.2.0-blue.svg?style=for-the-badge)](https://github.com/apiad/starter/releases)
[![License](https://img.shields.io/github/license/apiad/starter?style=for-the-badge&color=success)](LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg?style=for-the-badge)](https://github.com/apiad/starter/graphs/commit-activity)

**Clean your filesystem with precision.**

*A Python-based CLI utility that performs high-performance filesystem scanning to identify space-intensive directories and applies a heuristic scoring model to suggest data collection.*

</div>

---

## 🚀 Getting Started

The `gc` tool is built with modern Python tooling (`uv`).

### Installation

```bash
# Clone the repository
git clone https://github.com/apiad/gc.git
cd gc

# Install dependencies and build the project
uv sync
```

### Usage

By default, running `gc` will scan the current directory and provide a hierarchical size summary:

```bash
uv run gc .
```

#### Options:
- `--depth` / `-d`: Maximum display depth (default: 3).
- `--min-percent` / `-p`: Minimum size percentage of parent to show child (default: 0.05).
- `--limit` / `-l`: Maximum number of children to list individually (default: 4).
- `--min-size`: Minimum size in bytes to report.
- `--dry-run`: Show what would be collected without deleting.

---

## 🧠 The Core Philosophy

`gc` is more than a simple `du` clone. It uses a **Pipe-and-Filter** architecture to turn raw metadata into actionable deletion proposals:

1.  **Scanner (The Collector):** High-performance BFS scanning using `os.scandir`.
2.  **Heuristic Engine (The Mark Phase):** (Coming Soon) Scores nodes based on patterns, recency, and regenerability.
3.  **Aggregator (The Sweep Phase):** Bubbles up sizes and scores to reduce CLI noise.

---

## 🛠️ Development Lifecycle

The project is managed using a highly customized Gemini CLI agent framework. For more information on the framework and available commands, refer to [GEMINI.md](GEMINI.md).

### Standard Targets:
- `make lint`: Run Ruff checks.
- `make format`: Apply code formatting.
- `make test`: Execute the test suite.
- `make check`: Run Mypy static analysis.
- `make all`: Run all checks and tests.

## ⚓ The Hook System

The framework uses a robust hook system (`.gemini/hooks/`) that synchronizes the agent with your project state, ensuring continuous validation and journaling.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
