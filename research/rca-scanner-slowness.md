# RCA Report: Filesystem Scanner Performance Bottleneck

## Symptom
The application exhibits extreme slowness and high CPU utilization during the filesystem scanning phase, particularly when encountering directories with a large number of subdirectories (e.g., thousands of entries).

## Context
The scanner uses a Monte Carlo Tree Search (MCTS) approach to prioritize high-value directories. The core logic resides in `Scanner.scan`, which repeatedly calls `Scanner.mcts_iteration`. Each iteration starts from the root and descends to a leaf node by calling `Scanner.select_node` at each level.

## Investigation Log
1.  **Code Analysis**: 
    - `Scanner.select_node` iterates over all `available_children` of a node.
    - For each child, it calls `self.engine.get_matching_signature(child, self.signatures)`.
    - `HeuristicEngine.get_matching_signature` iterates over the entire list of ~20 signatures, performing a `pathlib.Path.match` (regex-based) for each.
2.  **Complexity Analysis**:
    - If a directory has $N$ subdirectories, exploring all of them requires at least $N$ iterations.
    - In iteration $i$ (where $i$ children remain to be explored), `select_node` performs $i$ signature matching calls.
    - Total calls per directory level: $\sum_{i=1}^{N} i = \frac{N(N+1)}{2}$.
    - Total matches: $O(N^2 \times S)$ where $S$ is the number of signatures.
3.  **Hypothesis Verification**: 
    - Architectural analysis confirms that nearly 500,000 signature matching calls are made just to explore one level of the tree with 1,000 children. Each call executes up to 20 `path.match` operations, leading to millions of regex evaluations.

## Root Cause
The root cause is **quadratic complexity in the selection phase of the MCTS loop**. Because `DirectoryNode` does not cache its matched signature, the scanner re-evaluates the same expensive regex patterns for every child node during every single MCTS iteration that passes through their parent.

## Impact
- **Performance**: Scan times scale poorly ($O(N^2)$) relative to the number of entries in a directory.
- **Resource Usage**: High CPU consumption due to redundant `fnmatch`/regex operations.
- **User Experience**: The UI becomes unresponsive or extremely slow to progress in deep/wide directory structures.

## Fix Recommendations
1.  **Signature Caching**: Add a `signature: Signature | None` field to `DirectoryNode`. Modify `Scanner._process_directory` to compute and store the matching signature once when the node is first discovered.
2.  **Refactor Selection**: Update `Scanner.select_node` to use the cached signature instead of calling the engine for every match check.
3.  **UI Throttle**: Consider throttling UI updates in `Scanner.scan` to ensure they don't saturate the event loop during high-speed iterations.
