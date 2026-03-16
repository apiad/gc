# Executive Report: Garbage Collection Signatures for Build Systems and ML Frameworks

## Executive Summary
This research identifies a comprehensive set of "Garbage Collection" signatures for modern development environments, specifically focusing on build systems, machine learning frameworks, and OS-level transient data. Key insights include:
- **Build Systems** (C++, Node.js, Rust) are the most frequent sources of disk bloat, with `node_modules` and `target/` being primary candidates for medium-priority cleanup (Priority 0.5-0.8).
- **ML Frameworks** (Hugging Face, PyTorch) present the highest potential for single-folder reclaimed space (10GB-100GB+), but require careful "stale" threshold management (60+ days) due to high re-download costs.
- **Heuristic Scoring** should be tiered based on **Regenerability** (1.0 for transient, 0.5 for downloads) and **Recency** (stale if >30 days for builds, >60 for models).
- **Safety** is paramount; we have identified critical "Never Touch" patterns (e.g., `.git/`, `.env`, system paths) that must be hardcoded into the `fsgc` protection list.

## Research Questions

### 1. Common Build System Artifacts & Caches
Detailed research on build system signatures can be found in: [build-systems.md](garbage-collection-signatures/build-systems.md)

*   **C/C++:** Primary patterns include `**/build/`, `**/out/`, and `**/CMakeFiles/`. These are highly regenerable (Priority 1.0) and typically safe to delete if older than 7-14 days.
*   **Java/JVM:** Maven uses `~/.m2/repository/` and Gradle uses `~/.gradle/caches/`. These can grow to 20GB+ and are mostly safe to prune (stale after 30-60 days), though sub-paths for local artifacts should be protected.
*   **JavaScript/Node.js:** Standard `**/node_modules/` is the primary target (Priority 0.8). Global caches in `~/.npm/_cacache/` and `~/.pnpm-store/` are significant (1-5GB) and safe to prune.
*   **Rust & Go:** Rust uses `**/target/` (Priority 1.0) and `~/.cargo/registry/`. Go uses `$GOMODCACHE` (usually `~/go/pkg/mod`). Both environments offer built-in clean commands, but the directories are safe for external scanning and pruning of stale entries (30+ days).

### 2. Machine Learning Framework Caches
Detailed research on ML cache signatures can be found in: [ml-caches.md](garbage-collection-signatures/ml-caches.md)

*   **Hugging Face:** Centralized in `~/.cache/huggingface/`. The `hub/` and `datasets/` folders are the largest (10GB-100GB+). Safe targets include `**/incomplete/` and `**/.locks/`. Models are regenerable (Priority 0.5) but re-downloading is expensive in terms of time/bandwidth. Stale threshold: 60+ days.
*   **PyTorch & TensorFlow:** PyTorch uses `~/.cache/torch/hub/checkpoints/`. TensorFlow Hub defaults to `/tmp/tfhub_modules/` or a user-defined `TFHUB_CACHE_DIR`. Both store large model binaries. Deleting these is safe but requires re-downloading. Stale threshold: 30-60 days.
*   **Kaggle:** Uses `~/.cache/kagglehub/` for datasets and models. Similar to others, it uses `.lock` and `.tmp` files for in-progress transfers which are safe to delete if the timestamp is old (>24h).

### 3. OS & Application Transient Data
Detailed research on OS-level signatures can be found in: [os-app-transient.md](garbage-collection-signatures/os-app-transient.md)

*   **Linux/MacOS:** Standard user caches are in `~/.cache/` (Linux) and `~/Library/Caches/` (MacOS). High-impact targets include browser caches (Chrome/Firefox) and Electron-based apps (Discord, Slack, VS Code). These are highly regenerable (Priority 1.0) and safe to prune if older than 14-30 days.
*   **Docker:** While direct filesystem deletion is risky, identifying `**/docker/overlay2/` or `**/docker/buildkit/` size impact is useful. Safer signatures include dangling image identifiers or cache layers that haven't been accessed in 30 days.
*   **Python Ecosystem:** Common development artifacts include `**/.tox/`, `**/.nox/`, `**/.pytest_cache/`, `**/.mypy_cache/`, and `**/.venv/`. These are highly regenerable (Priority 1.0) and can collectively take several GBs in a developer's workspace.
*   **Temp Folders:** `/tmp/` and `/var/tmp/` often contain stale sockets, lock files, and partial downloads. Standard OS behavior is to prune these on reboot, but for persistent systems, a 7-day stale threshold is common.

### 4. Heuristic Criteria & Signature Patterns
Detailed research on heuristic best practices can be found in: [heuristics-best-practices.md](garbage-collection-signatures/heuristics-best-practices.md)

*   **Regenerability Tiers:**
    *   **Priority 1.0 (High):** Purely transient data. Browser caches, OS thumbnails, `.pytest_cache`, `**/build/`, `**/__pycache__/`.
    *   **Priority 0.5 (Medium):** Downloaded but regenerable artifacts. `node_modules/`, Cargo `target/`, Hugging Face models, large datasets.
    *   **Priority 0.2 (Low):** Potentially dangerous or manual state. Local logs, session state, `.env` files.
*   **Stale Aging Thresholds:**
    *   Build Artifacts: 7-14 days.
    *   ML Models/Datasets: 60-90 days.
    *   OS Caches: 30 days.
    *   Temp Files: 7 days.
*   **Safety ("Never Touch" Patterns):**
    *   Critical OS paths: `/etc/`, `/boot/`, `/System/`.
    *   Sensitive user paths: `~/.ssh/`, `~/.gnupg/`, `~/.aws/`.
    *   Environment secrets: `**/.env`, `**/secrets.yaml`.
    *   Git state: `**/.git/` (to prevent repo corruption).

## Conclusions
The research confirms that a heuristic-based garbage collector can safely and effectively reclaim significant disk space by targeting well-known transient directories. Build artifacts and ML model caches are the "low-hanging fruit" of filesystem bloat. While most of these are safe to delete, the scoring model must distinguish between data that is "easy to recreate" (builds) and data that is "expensive to re-download" (ML models). A robust implementation must also respect OS-specific cache standards (XDG) and provide strong safety defaults to prevent corruption of version control or leakage of secrets.

## Recommendations
1.  **Immediate Action:** Update `config/signatures.yaml` with the prioritized patterns identified in this report (Build systems, ML caches, Python dev tools).
2.  **Scoring Tuning:** Implement the 3-tier Regenerability system in the `HeuristicEngine`.
3.  **Safety First:** Hardcode the "Never Touch" patterns into the `Scanner` or a global protection list to prevent accidental deletion of `.git` or `.env` files.
4.  **User Experience:** Group same-pattern findings (e.g., "All node_modules") in the TUI to reduce noise, as planned.
5.  **Follow-up:** Investigate "Growth Rate" tracking by persisting scan metadata, as suggested in the original design document.
