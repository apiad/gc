# Design Document: `gc` (Garbage Collector)

## 1. Objective

A Python-based CLI utility that performs high-performance filesystem scanning to identify space-intensive directories and applies a heuristic scoring model to suggest "Garbage Collection" (deletion) of transient or stale data.

## 2. System Architecture

The tool follows a **Pipe-and-Filter** architecture where data flows from raw metadata to a refined "Collection Proposal."

### A. The Scanner (The Collector)

* **Engine:** `concurrent.futures.ThreadPoolExecutor` using `os.scandir`.
* **Optimization:** Avoids `os.walk` to minimize object creation. Uses a **Breadth-First Search (BFS)** approach to allow the user to see top-level results immediately while deeper sub-directories are still being indexed.
* **Data Structure:** A `Trie` (Prefix Tree) or a `Directed Acyclic Graph (DAG)` representing the directory hierarchy, where each node aggregates the size of its children.

### B. The Heuristic Engine (The Mark Phase)

This component "marks" nodes for deletion based on a **Multi-Criteria Scoring Function**.

$$S(n) = w_1 \cdot P(n) + w_2 \cdot A(n) + w_3 \cdot R(n)$$

Where:

* $P(n)$: **Pattern Match Score.** Binary or weighted score if the directory name matches a "known transient" list (e.g., `node_modules` = 1.0, `Downloads` = 0.4).
* $A(n)$: **Recency Decay.** $1 - \frac{t_{now} - t_{access}}{t_{threshold}}$. Older files get higher scores for removal.
* $R(n)$: **Regenerability.** A constant based on the difficulty of recreating the data (e.g., `.cache` is 1.0, `src` is 0.0).

### C. The Aggregator (The Sweep Phase)

Instead of listing every file, `gc` bubbles up the scores. If a parent directory's children are 90% "garbage" by score, the tool suggests deleting the parent rather than individual files to reduce "CLI noise."

---

## 3. Component Specification

### Signature Map (Knowledge Base)

A decoupled configuration file (YAML) that defines what constitutes garbage.

```yaml
signatures:
  - name: "Python Bytecode"
    pattern: "**/__pycache__"
    priority: 1.0
  - name: "Node Dependencies"
    pattern: "**/node_modules"
    priority: 0.8
    min_age_days: 30

```

### State Persistence

To allow for "incremental scanning," `gc` will maintain a lightweight **Local Metadata Cache** (SQLite or MsgPack).

* **Purpose:** Compare $t_0$ scan with $t_1$ scan to show "Growth Rate" (e.g., "Your `.cache` grew by 4GB since yesterday").

---

## 4. User Interface Design (TUI)

Since we want "at a glance" clarity, the interface should use a **Hierarchical Density Map**.

* **Primary View:** A list of top-level directories sorted by `Size * Score`.
* **The "Proposal" Prompt:**
> `gc` has identified 14.2GB of collectable garbage.
> [X] ~/.cache/pip (2.1GB) - *Stale (>60 days)*
> [X] ~/dev/project-a/node_modules (1.2GB) - *Transient*
> [ ] ~/Downloads (8.0GB) - *Large, potentially manual review needed*
> **[Run Collection] [Dry Run] [Exit]**



---

## 5. Safety & Constraints

* **Filesystem Boundaries:** By default, `gc` should stay within a single mount point (`st_dev` check) to avoid scanning network drives or virtual filesystems like `/proc`.
* **Protection List:** A hardcoded "Never Touch" list (e.g., `/etc`, `/usr/bin`, `~/.ssh`).
* **Atomic Deletion:** Use trash-cli integration where available, or a staged deletion (moving to a `.gc_trash` folder) before final purging.
