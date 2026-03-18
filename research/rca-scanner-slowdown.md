# Root Cause Analysis (RCA) - Scanner Performance Degradation

## Symptom
The scanner's performance degrades and eventually stops as the directory tree grows wider, particularly at the root or top levels.

## Context
The issue was reported in the context of `Scanner.scan()` and `Scanner.mcts_iteration()`.
- **Files involved:** `src/fsgc/scanner.py`
- **Key functions:** `DirectoryNode.calculate_metadata()`, `Scanner.mcts_iteration()`, `Scanner.select_node()`.

## Investigation Summary
1.  **Complexity Bottleneck:** `DirectoryNode.calculate_metadata()` is $O(W)$ where $W$ is the number of children. Since it's called bottom-up in `mcts_iteration` for every node in the path (length $D$), each MCTS iteration performs $O(D \cdot W)$ work.
2.  **Blocking UI Updates:** The `scan()` generator's yield loop forces a root-level `calculate_metadata()` every 100ms. On wide roots, this synchronous iteration blocks the async event loop, preventing workers from enqueuing new results and causing the UI to "stutter" or stop.
3.  **Redundant Traversals:** `calculate_metadata()` is recursive. Even if intermediate nodes aren't dirty, the parent still iterates over all child references to check their state, which is costly when a directory has thousands of subfolders.

## Root Cause
The root cause is the **inefficient propagation of metadata updates** in wide trees. The scanner relies on full child iteration to aggregate sizes and completion ratios, which becomes a CPU-bound bottleneck that blocks the I/O-bound scanning workers.

## Proposed Strategy
1.  **Incremental Propagation:** Shift from a pull-based `calculate_metadata()` to a push-based incremental update. When a node's size or state changes, it should update its parent's totals directly ($O(1)$ per level).
2.  **Optimized UI Snapshots:** Use the incrementally maintained totals for the root snapshot instead of triggering a full tree traversal.
3.  **Lazy Metadata Sync:** Only perform full traversals for non-additive metrics (like `max_atime`) when explicitly requested or at the very end of the scan.
