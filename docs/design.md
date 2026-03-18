# High-Level Architecture and Design

**fsgc** is built on a "stochastic search" philosophy, prioritizing speed and interactivity over exhaustive enumeration. This document details the core components and architectural decisions that enable this performance.

---

## 🏗 Core Components

### 1. `Scanner` (Stochastic Engine)
The `Scanner` is the heart of **fsgc**. Instead of a standard Breadth-First Search (BFS), it uses **Monte Carlo Tree Search (MCTS)** principles to explore the filesystem:
*   **Selection:** The engine selects which subdirectory to descend into based on a multi-tiered heuristic.
*   **Expansion:** New nodes are added to the tree when a directory is visited for the first time.
*   **Backpropagation:** Once a leaf or deep subdirectory is reached, its size and metadata are bubbled up to the root.

### 2. `DirectoryNode` (Incremental Metadata)
To maintain a responsive UI, **fsgc** uses a push-based incremental propagation model:
*   Each node maintains its local `files_size` and a sum of its children's `confirmed_size`.
*   Whenever a child's size changes, it "bubbles up" the delta to its parent.
*   This ensures that the root node always has an $O(1)$ snapshot of the entire scanned tree.

### 3. `HeuristicEngine` (Scoring)
The `HeuristicEngine` applies a weighted scoring model to each directory:
*   **Pattern Match (60%):** Does the folder name match a known garbage pattern?
*   **Priority (30%):** How "safe" is it to delete this kind of garbage?
*   **Recency (10%):** When was the last time any file in this branch was modified or accessed?

### 4. `GCTrail` (Binary Cache)
Trails are lightweight binary files (`.gctrail`) stored in large directories. They provide "priors" for the scanner, allowing it to estimate sizes without visiting every subdirectory. See [**GCTrail Reference**](trail.md) for technical details.

---

## 🧭 Informed Search (MCTS)

The `Scanner` chooses which directory to explore using a two-tiered heuristic in `Scanner.select_node`:

1.  **Tier 1: Signatures:** If a directory matches a high-priority signature (e.g., `node_modules` or `target`), it is prioritized for exploration.
2.  **Tier 2: Historical Trail Data:** If a `.gctrail` file exists, the scanner prioritizes subdirectories that were historically the largest.
3.  **Fallback:** If no priors exist, it defaults to a greedy search for the largest estimated size among unvisited nodes.

---

## ⚡ Performance Optimization

*   **Bounded Worker Pool:** The scanner uses `asyncio.to_thread` and a configurable pool of workers to perform parallel MCTS explorations without being blocked by disk I/O.
*   **Structural Hashing:** Before trusting a `.gctrail` file, the scanner validates its `structural_hash` (derived from `mtime` and entry count). If the directory has changed significantly, the cache is invalidated.
*   **Stay-on-Mount:** By default, the scanner avoids crossing filesystem boundaries (mount points) to prevent unexpected traversals of network drives or large external volumes.

---

## 🔄 Data Flow Summary

```text
[Filesystem] --- (os.scandir) ---> [Scanner] 
                                      |
                                (MCTS Playouts)
                                      |
                                      v
 [DirectoryNode] <--- (Delta) --- [DirectoryNode] 
       |
  (O(1) Root)
       |
       v
  [Aggregator] ---> [TUI Rendering]
```
