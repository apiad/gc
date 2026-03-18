# GC Signatures and Sentinel Verification

The `signatures.yaml` file defines the "knowledge base" of **fsgc**, identifying which directories are garbage and how to verify them. This document explains the signature schema and how to customize it.

---

## 📜 Signature Schema

Each entry in `signatures.yaml` contains several fields to guide the heuristic engine:

| Field | Description |
| :--- | :--- |
| `name` | Human-readable name for the garbage group. |
| `pattern` | Glob pattern to match a directory (e.g., `**/node_modules`). |
| `priority` | Scoring weight between 0.0 and 1.0 (Higher is "more garbage"). |
| `min_age_days`| Minimum age of files (based on `mtime` and `atime`) before suggesting collection. |
| `sentinels` | List of filenames or glob patterns that must exist in or near the directory to verify it. |

### Example: Python Virtualenv
```yaml
- name: "Python Virtualenv"
  pattern: "**/.venv"
  priority: 0.9
  min_age_days: 7
  sentinels:
    - "pyvenv.cfg"
```
In this example, **fsgc** will only suggest deleting a `.venv` directory if it is at least 7 days old and contains a `pyvenv.cfg` file.

---

## 🛡 Sentinel Verification

To avoid false positives, **fsgc** uses a "Trust-but-Verify" approach for signatures. When a directory matches a `pattern`, the `HeuristicEngine` checks its contents for "evidence" of the defined `sentinels`.

### Why Sentinels?
Caches and build artifacts often have common names (like `build`, `dist`, or `bin`). Without sentinels, **fsgc** might suggest deleting a user's source folder named `build`. Sentinels ensure the context is correct:
*   **Node.js:** Verifies `node_modules` by looking for a `package.json` file.
*   **Rust:** Verifies the `target` directory by looking for `CACHEDIR.TAG` or `.rustc_info.json`.
*   **C#:** Verifies `bin` and `obj` by looking for `.dll` or `.pdb` files.

---

## ⚙ Customizing Signatures

Users can add their own signatures to `src/fsgc/signatures.yaml`. After modification, the changes are applied immediately during the next `gc scan`.

### Tips for Effective Signatures:
*   **Use `**/` Prefix:** For patterns meant to be found anywhere in the tree.
*   **Specific Sentinels:** Prefer unique filenames (like `pyvenv.cfg`) over common extensions (`*.txt`) for better verification accuracy.
*   **Conservative Priority:** Start with a lower priority (e.g., `0.5`) for new signatures until you are confident in their accuracy.

---

## 🏗 Supported Ecosystems

**fsgc** ships with built-in signatures for:
- **Python:** `.venv`, `__pycache__`, `.pytest_cache`, `.tox`, etc.
- **Node.js:** `node_modules`, `.npm`, `.yarn/cache`.
- **Rust:** `target`, `.cargo/registry`.
- **Java:** `.m2/repository`, `.gradle/caches`.
- **C# / .NET:** `bin`, `obj`.
- **OS Metadata:** `.DS_Store`, `.thumbnails`.
- **Machine Learning:** Hugging Face and PyTorch caches.
