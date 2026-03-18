# Implementation Plan: Incremental Metadata Propagation

This plan addresses the performance bottleneck where the scanner's $O(D \cdot W)$ metadata calculation blocks the async event loop in wide directory trees. By shifting to a push-based incremental update model, we reduce UI snapshot complexity to $O(1)$ and update propagation to $O(D)$.

## Objective
Replace the recursive, pull-based `calculate_metadata()` with a push-based system where each `DirectoryNode` updates its parent incrementally upon change.

## Architectural Impact
- **Performance**: UI refreshes become $O(1)$ by reading root fields directly. MCTS backpropagation becomes $O(D)$.
- **Concurrency**: Updates remain synchronous within the `asyncio` loop, ensuring thread-safety without locks.
- **Derived State**: `is_fully_explored` and `ScanState.FINISHED` propagate automatically from leaves to root.

## File Operations

### `src/fsgc/scanner.py`
- **Modify `DirectoryNode`**:
  - Add `parent: "DirectoryNode | None" = field(default=None, repr=False)`.
  - Add internal counters: `_sum_child_confirmed_size`, `_sum_child_estimated_size`, `_sum_child_completion_ratio`, and `_unexplored_children_count`.
  - Remove `dirty` flag and `_metadata` cache.
- **Implement Methods**:
  - `update_metadata()`: Calculates local totals and calls `parent.propagate_child_update()` if values changed.
  - `propagate_child_update(delta_confirmed, delta_estimated, delta_ratio, became_fully_explored, atime, mtime)`: Updates internal counters and triggers `update_metadata()`.
- **Refactor `Scanner`**:
  - `_process_directory`: Call `node.update_metadata()` once after all entries are processed.
  - `mcts_iteration`: Remove manual `dirty` and `calculate_metadata` calls.
  - `scan()`: Yield the root node directly without calling `calculate_metadata`.

## Step-by-Step Execution

1.  **Step 1: Data Model Update**: Add `parent` and tracking counters to `DirectoryNode`. Use `field(repr=False)` for `parent` to avoid recursion in logs.
2.  **Step 2: Propagation Logic**: Implement the delta-based update flow. When a node's size increases by $X$, it informs the parent to increase its total by $X$.
3.  **Step 3: State Propagation**: When a child's `_unexplored_children_count` reaches 0, it signals the parent to decrement its own count. If the parent hits 0 and is processed, it becomes `FINISHED`.
4.  **Step 4: Scanner Integration**: Update the worker and MCTS logic to trigger these updates only when a node's primary state (files size or processing status) changes.
5.  **Step 5: Compatibility Layer**: Keep `calculate_metadata()` as a simple getter for the existing UI and aggregator code to prevent widespread breakage.

## Testing Strategy
- **Performance Regression**: Verify that `Scanner.scan()` yield times do not increase with directory width.
- **Metadata Accuracy**: Use `tests/test_scanner.py` to ensure `confirmed_size` and `atime/mtime` still match the filesystem exactly.
- **MCTS Stability**: Ensure nodes are still correctly marked as `FINISHED` and `.gctrail` files are generated upon completion.
