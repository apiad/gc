# OS and Application-Level Transient Data Signatures

This document outlines the standard locations, identification patterns, and safety considerations for transient data across major operating systems and the Python development ecosystem.

## 1. Linux Transient Data

### Standard Paths
| Path | Purpose | Persistence | Recommendation |
| :--- | :--- | :--- | :--- |
| `~/.cache` | User application caches (XDG standard). | Persistent | Safe to delete contents; apps regenerate. |
| `/tmp` | Short-term temporary files. | Often cleared on reboot | Volatile; clean with caution if uptime is high. |
| `/var/tmp` | Long-term temporary files. | Persistent (per FHS) | Safe to delete files older than a threshold. |
| `/var/cache` | System-level caches (e.g., `apt`, `pacman`). | Persistent | Use package manager tools to clean. |

### Identifying "Stale" Files
Staleness is typically defined by **Access Time (`atime`)** or **Modification Time (`mtime`)**.
- **Commands:**
  - Find files not accessed in 30 days: `find ~/.cache -type f -atime +30`
  - Find files not modified in 14 days: `find /var/tmp -type f -mtime +14`
- **System Automation:** Modern Linux systems use `systemd-tmpfiles`. Configuration is found in `/usr/lib/tmpfiles.d/` and `/etc/tmpfiles.d/`.
  - Dry run cleanup: `systemd-tmpfiles --clean --dry-run`

---

## 2. MacOS Transient Data

### Standard Paths
| Path | Purpose | Persistence |
| :--- | :--- | :--- |
| `~/Library/Caches` | User-level application caches. | Persistent |
| `~/Library/Logs` | User-level application logs. | Persistent |
| `/Library/Caches` | System-wide caches. | Persistent |
| `~/Library/Containers/*/Data/Library/Caches` | Sandboxed app caches. | Persistent |

### High-Impact Developer Locations
- **Xcode Derived Data:** `~/Library/Developer/Xcode/DerivedData/*` (Can grow to tens of GBs).
- **Homebrew Cache:** `~/Library/Caches/Homebrew/` or output of `brew --cache`.
- **CocoaPods:** `~/Library/Caches/CocoaPods/`.

### Native Cleanup
Booting into **Safe Mode** (holding Shift on Intel, Power button on Apple Silicon) triggers native system cache clearing and disk repairs.

---

## 3. Docker Transient Data

Identifying Docker data via filesystem signatures is useful for identifying "orphaned" data when the Docker daemon is unreachable or for external monitoring.

### Filesystem Signatures (Default: `/var/lib/docker/`)
| Data Type | Path Signature | Key File / Indicator |
| :--- | :--- | :--- |
| **Build Cache** | `buildkit/` | `metadata.db` (BoltDB), `snapshots/` folder. |
| **Volumes** | `volumes/<name>/_data/` | Presence of `_data` directory; Anonymous volumes use 64-char hex names. |
| **Images** | `image/<driver>/imagedb/` | Content-addressable layers in `overlay2/`. |
| **Dangling** | `image/<driver>/repositories.json` | Image IDs present in `imagedb` but **missing** from `repositories.json` are dangling. |

### Safety Note
Directly deleting files in `/var/lib/docker` is **strongly discouraged** as it corrupts the Docker daemon's state. 
- **Preferred Method:** `docker system prune -a --volumes`
- **Filesystem Identification:** Use to flag space-hogs, then use API/CLI to remove.

---

## 4. Python Ecosystem Caches

Python tools generate predictable hidden directories that are generally safe to delete (caches will be rebuilt on next run).

### Common Signatures
| Directory | Tool | Impact of Deletion |
| :--- | :--- | :--- |
| `.pytest_cache` | `pytest` | Loses "last failed" state (`--lf`) and minor speed optimizations. |
| `.mypy_cache` | `mypy` | Forces full re-analysis of the project (slow for large codebases). |
| `.tox` / `.nox` | `tox` / `nox` | Removes virtualenvs; triggers full re-download and install of dependencies. |
| `.venv` / `venv` | Python | Removes the virtual environment and all installed packages. |
| `__pycache__` | Python | Removes compiled bytecode; slightly slows next import. |

### High-Impact Patterns
- **Build Artifacts:** `dist/`, `build/`, and `*.egg-info/`.
- **Deep Cleanup:** `git clean -xfd` (Warning: deletes all untracked files, including `.env`).

---

## 5. High-Impact Application Patterns (Browsers & Electron)

Browsers and Electron-based apps (Slack, Discord, VS Code) are often the largest contributors to disk bloat.

### Linux Locations
- **Chrome/Brave:** `~/.cache/google-chrome/` or `~/.cache/BraveSoftware/`
- **Firefox:** `~/.cache/mozilla/firefox/<profile>/cache2/`
- **Electron:** Often misplaces cache in `~/.config/<app-name>/Cache` instead of `~/.cache`.

### MacOS Locations
- **Chrome/Brave:** `~/Library/Caches/Google/Chrome/`
- **Safari:** `~/Library/Caches/com.apple.Safari/`
- **Electron:** `~/Library/Caches/<bundle-id>/` or `~/Library/Application Support/<app-name>/Cache`.

---

## 6. Recommended "Stale" Thresholds

| Data Volatility | Threshold | Best Use Case |
| :--- | :--- | :--- |
| **High** | 24 Hours | Session files, `/tmp`, Lock files. |
| **Medium** | 7 - 14 Days | Application logs, general browser cache. |
| **Low** | 30 - 90 Days | Package manager caches (`pip`, `npm`), Docker build caches, `tox` envs. |
| **Immutable** | 1 Year | Versioned static assets (e.g., `main.v123.js`). |

### Deletion Safety Tiers
1.  **Pure Cache (Tier 1):** `__pycache__`, `.pytest_cache`, `.mypy_cache`. Always safe.
2.  **Stateful Cache (Tier 2):** Browser caches, Docker build caches. Safe, but causes network/CPU usage on refresh.
3.  **Environment (Tier 3):** `.venv`, `.tox`. Safe if `requirements.txt`/`pyproject.toml` exists.
4.  **System/Shared (Tier 4):** `/var/tmp`, `/tmp`. Safe for old files, but check for active lock files first.
