## 1. The Stochastic Real-Time Search Engine

Traditional tools perform a deterministic, linear crawl. **`gc`** treats the filesystem as a **Search Space** where the objective is to maximize "Value Discovered" ($V_d$) per "I/O Operation" ($I_o$).

### A. The Heuristic Prioritization

The search does not start at index $0$. It initializes a **Global Priority Queue (GPQ)** seeded with three types of priors:

1. **Static Priors:** Hardcoded high-probability paths (e.g., `~/.cache`, `~/Downloads`).
2. **Contextual Priors:** Dynamic detection of project roots (e.g., any folder containing `.git/` or `node_modules/`).
3. **Historical Priors:** Data extracted from existing `.gctrail` files.

### B. The "Scout & Crawler" Execution Model

The search operates in two concurrent phases to ensure the "First-Second" UI response:

* **The Scout (Stochastic Probes):** * Launches high-concurrency, shallow-depth probes.
* If a scout hits a directory matching a high-weight prior, it performs a `scandir` and immediately reports any files $>10$ MB.
* It samples the "scent" of a directory; if the density of large files is high, it re-prioritizes that branch in the GPQ.


* **The Crawler (Background Verification):**
* Follows behind the scouts to perform the exhaustive walk.
* It fills in the "Missing Mass"—the aggregate size of the millions of tiny files ($<10$ MB) that the scouts ignored.



---

## 2. `.gctrail` Logic: The "Decentralized Scent"

To achieve $O(1)$ performance on subsequent runs without a centralized database, `gc` utilizes distributed sidecar files.

### A. Anatomical Structure of a `.gctrail`

Stored as a fixed-width binary blob (via Python `struct`), a trail contains:

* **Timestamp:** The epoch of the last scan.
* **Structural Hash:** A checksum of the directory's `mtime` and `inode` count.
* **The "Big Fish" List:** Metadata for the Top-N files found ($>10$ MB).
* **Aggregates:** Pre-computed sums of "noise" (small files) and "reconstructible" value.

### B. The "Trust but Verify" Protocol

When the search engine encounters a `.gctrail`, it follows this logic:

1. **The Snapshot (0ms):** The UI immediately renders the folder's state using the trail data. This is marked as a **"Ghost"** state.
2. **The Inode Validation:** A Scout thread performs a `stat()` on the directory.
* **IF** `dir.mtime == trail.timestamp`: The "Ghost" is promoted to **"Verified"**. The crawler skips this subtree entirely.
* **IF** `dir.mtime > trail.timestamp`: The "Ghost" remains, but the branch is flagged as **"Stale"**. The Scout samples the "Big Fish" list; if the largest files are still present/unchanged, the UI stays stable while the Crawler re-scans the "noise."



---

## 3. Mathematical Optimization: The Convergence

The goal of the stochastic engine is to reach **90% accuracy in 10% of the time**.

By prioritizing files $>10$ MB (which often account for $>90\%$ of disk usage but $<1\%$ of total file count), the tool achieves a "Bloom" effect where the most actionable data appears almost instantly, while the "perfect" `du`-style accuracy converges in the background.

### Why this works in Python:

By offloading the "Heavy Crawl" to a `ThreadPoolExecutor` and using `asyncio` for the "Scout" probes, we ensure the **Textual TUI** never drops a frame. The TUI simply listens to a `Queue` of "Discovery Events" and updates the Sunflower visualization reactively.
