# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-03-15

### Added
- **Core Package (`fsgc`):** Initial implementation of the "Garbage Collector" CLI utility.
- **Scanner Engine:** High-performance filesystem scanner using `os.scandir` and a Breadth-First Search (BFS) approach.
- **Tree-based Aggregation:** Logic to build a directory tree and aggregate sizes from the bottom up.
- **Hierarchical Summary:** Tree-like TUI summary using `Rich`, featuring configurable depth, child limits, and size-based grouping.
- **Human-Readable Sizes:** Automatic formatting of byte counts into KB, MB, GB, etc., across the entire CLI output.
- **Modern Tooling:** Project initialized with `uv`, `ruff`, `mypy`, and `pytest`.

### Changed
- Refactored CLI to use `scan` as the default command when invoked without subcommands.
- Updated `makefile` with standardized `lint`, `test`, `check`, and `format` targets.

## [0.11.0] - 2026-03-11

...
