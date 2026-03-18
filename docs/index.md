# fsgc: The Stochastic Filesystem Garbage Collector

**fsgc** is a high-performance, heuristic-based filesystem scanner designed to identify and reclaim space from "garbage" directories—caches, build artifacts, and temporary files—that accumulate in modern development environments.

Unlike traditional tools like `du` or `find`, which exhaustively visit every file, **fsgc** uses **Monte Carlo Tree Search (MCTS)** and **Stochastic Scanning** to prioritize high-value branches, providing near-instant estimates for massive directory trees.

---

## 🧠 The Philosophy: "The Architect in the Machine"

In a world of multi-gigabyte `node_modules`, `target` folders, and `.cache` directories, exhaustive scanning is often too slow for interactive use. **fsgc** treats the filesystem as a tree to be explored strategically.

### Key Concepts

*   **Stochastic Scanning:** Instead of a linear BFS/DFS, the scanner "plays out" multiple paths from the root, guided by heuristics and historical data. This allows it to discover large garbage clusters early.
*   **Trust-but-Verify:** The tool provides "Confirmed" sizes (actually seen on disk) vs "Estimated" sizes (predicted based on historical `.gctrail` data). As the scan progresses, estimates converge to reality.
*   **Signature-Driven:** A robust `signatures.yaml` engine identifies garbage patterns (e.g., Python `__pycache__`, Rust `target`) and verifies them using "sentinels" (e.g., ensuring a `package.json` exists before suggesting the deletion of `node_modules`).

---

## 🚀 Main Features

*   **Real-time TUI Updates:** Watch the scan progress with a live-updating tree view and throughput indicators (MB/s).
*   **Interactive Selection:** Review a categorized proposal of garbage to be collected, grouped by signature and prioritized by size.
*   **Incremental Propagation:** Architectural support for $O(1)$ root snapshots ensures the UI remains responsive even when scanning millions of entries.
*   **Trail Persistence:** Automatically saves lightweight `.gctrail` binary files in large directories to "remember" their structure for the next scan.

---

## 📖 Quick Start

```bash
# Scan the current directory
uvx fsgc scan .

# Scan with a dry-run to see what would be deleted
uvx fsgc scan ~/Projects --dry-run

# Inspect a specific directory's historical trail
uvx fsgc inspect .
```

---

## 📂 Documentation

- [**Installation & Deployment**](deploy.md): Get up and running in seconds.
- [**High-Level Design**](design.md): Deep dive into the MCTS engine and incremental architecture.
- [**Development Guide**](develop.md): Workflow, testing, and contribution standards.
- [**GC Signatures**](signatures.md): How to customize and extend the garbage detection engine.
- [**GCTrail Reference**](trail.md): Technical details of the binary cache schema.
