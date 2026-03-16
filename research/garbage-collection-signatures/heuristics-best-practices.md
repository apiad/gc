# Heuristic Criteria for Garbage Collection Signatures

This document synthesizes industry best practices and research-backed heuristic criteria for identifying, prioritizing, and safely cleaning up stale files and directories.

## 1. Regenerability: Priority Tiers

The regenerability of data is the primary factor in determining how aggressive a garbage collection (GC) policy should be. We use a 3-tier priority system (Weighting Factor) to guide automated cleanup tools.

| Tier | Weight | Category | Description | Examples |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | **1.0** | **Purely Transient** | Data that can be recreated instantly or with minimal resource consumption. Deletion causes only a minor, one-time latency hit. | Browser caches, image thumbnails (`.thumbnails`), temporary session files, UI state caches, `.pyc` files. |
| **Tier 2** | **0.5** | **Expensive to Recreate** | Data that can be recreated, but requires significant time, computation, or network bandwidth. Often requires a "trigger" (like a build command). | `node_modules`, `target/` (Rust), `build/` (Java/C++), downloaded ML model weights, large datasets from remote sources. |
| **Tier 3** | **0.2** | **Manual / Dangerous** | Data that is technically regenerable but involves a high risk of failure, manual reconfiguration, or loss of unique transient context. | `.env` files, local-only logs, un-pushed git commits, custom configuration files, partially downloaded files (non-resumable). |

### Decision Logic
- **Weight 1.0:** GC can happen automatically when disk pressure is detected.
- **Weight 0.5:** GC should only happen during scheduled maintenance or when disk space is critically low (e.g., < 5%).
- **Weight 0.2:** GC should **never** be automated without explicit user confirmation or a very long "stale" period (e.g., 180+ days).

---

## 2. Aging Thresholds (Stale Periods)

Typical "stale" periods used in the industry to balance storage efficiency and developer productivity.

### 🏗️ Build Artifacts & Development
- **Feature/PR Builds:** **7–14 days**. After a PR is merged or closed, artifacts are usually obsolete.
- **Continuous Integration (CI) Caches:** **30 days**. Most CI providers (GitHub Actions, GitLab) expire caches after 30 days of inactivity.
- **Release Candidates:** **90–180 days**. Kept until the major version is confirmed stable.
- **Production Releases:** **1–3 years** (or "Forever"). Often required for compliance and rollbacks.

### 🤖 ML Models & Data Science
- **Experimental Models:** **30 days**. Most experiments are superseded quickly.
- **Staging Models:** **90 days** or "Last 5 versions". A version-based cutoff is often more effective than a time-based one.
- **Training Logs/Metrics:** **90 days**. Summarized metrics are kept longer, but raw high-frequency logs (e.g., TensorBoard) are purged sooner.

### 💻 OS & System Caches
- **Package Manager Caches (`apt`, `brew`, `dnf`):** **30–60 days**.
- **System Logs (`journald`):** Usually capped by size (e.g., 1GB) or **90 days**.
- **Temporary Directories (`/tmp`, `Windows/Temp`):** **7 days** (or upon reboot). Files in `/tmp` are generally expected to be ephemeral.

### 📂 User Downloads & General Files
- **Downloads Folder:** **30–90 days** for files not accessed or modified.
- **Browser Cache:** **7–14 days** for mutable content; immutable assets may stay until disk pressure triggers a cleanup.

---

## 3. Glob Optimization: Best Practices

Effective GC requires efficient searching. Cross-platform glob patterns must be performant and safe.

### Best Practices for Performance
1.  **Include + Separate Ignore:** Most modern engines (e.g., `fast-glob`, `ripgrep`) perform better when you provide a broad include pattern and a specific list of ignore patterns rather than a complex negative glob.
2.  **Trailing Slashes:** Use a trailing slash for directories (e.g., `node_modules/`). This allows the engine to skip entering the directory entirely, saving thousands of syscalls.
3.  **Root-Relative Patterns:** If you know a directory like `.git` is only at the root, use `/.git/` instead of `**/.git/`.
4.  **Forward Slashes:** Always use `/` as the separator. Engines on Windows (like `pathlib` or `fast-glob`) normalize these automatically.

### Effective Target Identification (Example)
To find `node_modules` while avoiding sensitive directories like `.git` or `.ssh`:
- **Target:** `**/node_modules/**`
- **Exclusions:**
  - `**/.git/**` (Stops traversal into git history)
  - `**/.ssh/**` (Security boundary)
  - `**/.gnupg/**` (Security boundary)
  - `**/Library/**` (macOS system/app data)
  - `**/AppData/**` (Windows app data)

---

## 4. Safety: The "Never-Touch" List

Automated tools must strictly avoid these directories to prevent system failure, security breaches, or loss of critical user data.

### 🐧 Linux
- `/boot`: Essential kernel and bootloader files.
- `/etc`: System-wide configuration.
- `/proc`, `/sys`, `/dev`: Virtual filesystems (interface to kernel).
- `/bin`, `/sbin`, `/lib`, `/lib64`: Essential system binaries.
- `/var/lib`: Application state (e.g., databases, package manager state).
- `/root`: Root user's home directory.

### 🍎 macOS
- `/System`: Signed, read-only system files.
- `/Library/Preferences`: System-wide settings.
- `~/Library/Application Support`: Critical app databases.
- `~/Library/Containers`: Sandboxed app data.
- `~/Library/Mobile Documents`: **iCloud Drive** local cache (deleting here may trigger cloud deletion).

### 🪟 Windows
- `C:\Windows\System32`: Core OS binaries.
- `C:\Windows\WinSxS`: Side-by-Side component store (deleting manually breaks Windows Updates).
- `C:\ProgramData`: Shared application settings.
- `C:\Users\[User]\AppData\Roaming`: User profiles and persistent settings.
- `C:\System Volume Information`: System Restore points.
- `$RECYCLE.BIN`: Recycle bin metadata.

### 🛡️ User-Level Safety
- `~/.ssh`: SSH keys and known hosts.
- `~/.gnupg`: GPG keys.
- `~/.aws`, `~/.azure`, `~/.kube`: Cloud provider credentials.
- `~/.bashrc`, `~/.zshrc`: Shell configuration scripts.
- `**/.env`: Local environment secrets (API keys, DB passwords).
