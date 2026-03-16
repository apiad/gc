# Plan: Implement Canonical MCTS Exploration

This plan refines the filesystem search strategy to use a canonical Monte Carlo Tree Search (MCTS) approach for deterministic, depth-first-like exploration.

## 1. Objective
Implement a single-threaded, iterative MCTS loop that performs one full branch descent per iteration, prioritizing high-value directories (based on signatures and cache) while ensuring the entire tree is eventually verified.

## 2. Technical Architecture

### 2.1 Data Model Enhancements (`src/fsgc/scanner.py`)
- **`ScanState` Updates**:
    - `UNVERIFIED`: Initial state (replacing/merging with `UNSCANNED`).
    - `EXPLORING`: Active state for the branch being descended in the current iteration.
    - `VERIFIED`: Final state, only set when the ENTIRE subtree is fully explored.
- **`DirectoryNode` Metrics**:
    - `visits: int`: Number of times this node (or descendants) has been part of an iteration.
    - `total_reward: float`: Backpropagated "Garbage Value" (Confirmed Size * Heuristic Score).
    - `confirmed_size: int`: Sum of local files + sizes of all `VERIFIED` children.
    - `estimated_size: int`: `confirmed_size` + (Heuristic hints/Cache for unexplored children).
    - `is_fully_explored: bool`: True if all children are `VERIFIED`.

### 2.2 MCTS Iteration Logic
- **Selection (Downwards)**:
    - Use **UCT (Upper Confidence Bound applied to Trees)**:
      `Score = (total_reward / visits) + C * Heuristic * sqrt(ln(parent_visits) / visits)`.
    - `Heuristic` is a combination of `GC Trail Cache` and `Engine Signatures`.
    - Mark nodes on the path as `EXPLORING`.
- **Expansion**:
    - Descend until a leaf or an unexpanded node.
    - Perform a physical `os.scandir`. Create children nodes, but do not recurse into them in this iteration.
- **Backpropagation (Upwards)**:
    - Update `visits` and `total_reward`.
    - Mark nodes as `UNVERIFIED` (reverting from `EXPLORING`).
    - Recalculate `confirmed_size` and `estimated_size`.
    - If `is_fully_explored`, transition state to `VERIFIED`.

### 2.3 UI & Feedback (`src/fsgc/ui/formatter.py`)
- Highlight the `EXPLORING` path in the live tree summary.
- Display `Confirmed Size` with a "completion percentage" relative to `Estimated Size`.

## 3. Implementation Phases

1. **Phase 1: Metric Tracking**: Add visits, rewards, and size counters to `DirectoryNode`.
2. **Phase 2: Canonical Loop**: Replace `PriorityQueue` with a synchronous `while not root.is_fully_explored` loop calling `mcts_iteration`.
3. **Phase 3: UCT & Heuristics**: Implement the `select_node` logic using UCT and Engine scores.
4. **Phase 4: State Propagation**: Implement the bottom-up `VERIFIED` propagation logic.
5. **Phase 5: UI Polish**: Update the renderer to visualize the active MCTS branch.

## 4. Verification Plan
- **Unit Tests**:
    - Verify UCT selection prioritizes unvisited nodes.
    - Verify `confirmed_size` updates correctly as children become `VERIFIED`.
- **Integration Tests**:
    - Run on a mock filesystem to ensure the search terminates only when 100% explored.
