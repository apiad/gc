# Plan: Fix Scanner Performance Bottleneck

This plan addresses the quadratic complexity bottleneck in the filesystem scanner by implementing signature caching, optimizing heuristic matching, and throttling UI updates.

## 1. Objective
Reduce scanner selection complexity from $O(N^2)$ to $O(N)$ and minimize CPU overhead from redundant UI rendering and signature matching.

## 2. Technical Strategy

### 2.1 Signature Caching (`src/fsgc/scanner.py`)
- Add `signature: Signature | None = None` to the `DirectoryNode` dataclass.
- Update `Scanner._process_directory`: Immediately after a `child_node` is created, assign its signature using `self.engine.get_matching_signature(child_node, self.signatures)`.
- Update `Scanner.scan`: Assign the signature for the `root_node` during initialization.
- Update `Scanner.select_node`: Use the cached `child.signature` instead of calling the engine's matching logic.

### 2.2 Matching Optimization (`src/fsgc/engine.py`)
- Refactor `HeuristicEngine` to pre-identify "simple" signatures (e.g., those matching only by exact directory name like `**/node_modules`).
- Use `node.path.name == pattern` as a fast-path for these simple signatures, falling back to `node.path.match(pattern)` only for complex globs.
- Ensure `apply_scoring` respects the cached `node.signature`.

### 2.3 UI Throttling (`src/fsgc/__main__.py`)
- Implement time-based throttling in the `_do_scan` live update loop.
- Limit `live.update` and tree summarization to a maximum of **4 times per second** (250ms minimum interval).

## 3. Implementation Phases

1.  **Phase 1: Node Caching**: Modify `DirectoryNode` and `Scanner` to store and populate signatures.
2.  **Phase 2: Selection Refactor**: Update `select_node` to utilize the cache.
3.  **Phase 3: Engine Optimization**: Implement the matching fast-path in `HeuristicEngine`.
4.  **Phase 4: UI Polish**: Add the 250ms throttle to the CLI `scan` command.

## 4. Verification Plan
- **Correctness**: Run `make test` to ensure matching and MCTS logic remain sound.
- **Performance**: Profile a scan on a wide directory structure (e.g., a node project or large repo) to confirm CPU usage reduction.
- **UI Responsiveness**: Verify the TUI updates smoothly at the throttled rate without jittering.
