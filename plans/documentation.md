# Documentation Strategy: fsgc (File System Garbage Collector)

This plan outlines the creation of comprehensive, user-first documentation for the `fsgc` project, highlighting its "Stochastic Scanner" concept and providing clear paths for both users and developers.

## Objective
Establish a unified documentation suite in `docs/` that explains the tool's purpose, usage, architecture, and contribution guidelines.

## Target Audience
- **Users (Primary):** Developers and system administrators looking to clean their disks safely and efficiently.
- **Developers (Secondary):** Contributors looking to expand signatures, improve MCTS logic, or port the tool to other platforms.

## Proposed Documentation Structure

### 1. `docs/index.md` (Overview)
- **Concept:** "The Architect in the Machine" — Why MCTS-based scanning is superior to standard `du`.
- **Key Features:** Stochastic Scanning, Trust-but-Verify progress, Interactive Selection.
- **Use Cases:** Cleaning local dev environments, identifying "shadow" build caches, managing OS-level transients.

### 2. `docs/deploy.md` (Installation & Usage)
- **User Installation:** `uvx fsgc` (recommended) or `pipx install fsgc`.
- **Developer Installation:** `git clone` followed by `uv sync` or `pip install -e .`.
- **CLI Reference:**
    - `gc scan`: Options for workers, depth, size thresholds, and age.
    - `gc inspect`: How to view `.gctrail` file contents.
- **Environment:** Linux/macOS support (POSIX filesystem assumptions).

### 3. `docs/design.md` (High-Level Architecture)
- **Data Flow:** `Scanner` (MCTS Playouts) -> `DirectoryNode` (Incremental Metadata) -> `HeuristicEngine` (Scoring).
- **Informed Search:** How `GCTrail` and `signatures.yaml` (Tier 1/Tier 2) drive the selection process.
- **Performance:** $O(1)$ root snapshots via upward push-based propagation.

### 4. `docs/develop.md` (Development Guide)
- **Git Workflow:** Feature branches, TCR protocol, and PR expectations.
- **Testing:** `pytest` suites, async test patterns, and coverage mandates.
- **Code Standards:** `ruff`, `mypy`, and docstring conventions.

### 5. `docs/signatures.md` (GC Signatures)
- **Configuration:** Deep dive into `signatures.yaml`.
- **Sentinel Verification:** How the tool avoids false positives by checking for specific files (e.g., `package.json` for `node_modules`).
- **Customization:** Guide for users to add their own garbage patterns.

### 6. `docs/trail.md` (GCTrail Reference)
- **Binary Schema:** Description of the `GCTrail` format.
- **Structural Hashing:** How `mtime` and `entry_count` are used for quick cache invalidation.

## Verification
- Ensure all commands in `deploy.md` are tested.
- Verify architectural diagrams or descriptions in `design.md` match `src/fsgc/`.
- Ensure `develop.md` aligns with current `makefile` and `TASKS.md` practices.
