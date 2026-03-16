# MCTS Search Strategy Implementation Plan

This plan outlines the replacement of the current stochastic priority-queue-based filesystem search with an **Informed Monte Carlo Tree Search (MCTS)** model. The goal is to optimize for the discovery of large, deletable files/directories by treating the filesystem exploration as a search problem where "reward" is the efficiency of finding garbage.

## 1. Objective
Maximize the rate of discovery (Verified Deletable Size / Time) of garbage items by using a single-threaded MCTS to prioritize branches with high estimated potential (priors from signatures and trails).

## 2. Architectural Impact
-   **Scanner Logic:** Transitions from a concurrent worker model with a global priority queue to a single-threaded loop MCTS model.
-   **Node State:** `DirectoryNode` will now track search-specific metrics: visits, total reward (verified deletable size), total time spent, and estimated size from priors.
-   **Heuristic Integration:** The `HeuristicEngine` becomes a core component of the search loop to calculate the "reward" for each node during exploration.
-   **UI:** Display will shift to show "Verified Size" vs "Estimated Total Size" for each branch, reflecting MCTS metrics.

## 3. File Operations

### Modified Files:
-   `src/fsgc/scanner.py`: Major overhaul of `Scanner` to implement MCTS phases (Selection, Expansion, Simulation, Backpropagation) and update `DirectoryNode`.
-   `src/fsgc/engine.py`: Refactor to allow fast scoring of individual paths/nodes during the MCTS simulation phase.
-   `src/fsgc/aggregator.py`: Update `summarize_tree` to aggregate MCTS-specific metrics (estimated vs verified size).
-   `src/fsgc/ui/formatter.py`: Update the TUI (Rich Tree) to show verified vs estimated progress visually.
-   `src/fsgc/__main__.py`: Update `scan` command to initialize `HeuristicEngine` earlier and pass it to the `Scanner`.

## 4. Step-by-Step Execution

### Step 1: Augment `DirectoryNode`
Update `src/fsgc/scanner.py` to include MCTS metrics in `DirectoryNode`.
-   `visits: int = 0`: Number of times this node was part of a selection path.
-   `total_reward: float = 0.0`: Cumulative "verified deletable size" discovered.
-   `total_time: float = 0.0`: Cumulative time (seconds) spent scanning.
-   `estimated_size: int = 0`: Initial size estimate from `.gctrail` or heuristics.
-   `heuristic_score: float = 0.0`: Cached score from `HeuristicEngine`.
-   `is_fully_explored: bool = False`: Flag for when the entire subtree is verified.

### Step 2: Update `HeuristicEngine`
Update `src/fsgc/engine.py` to allow scoring a node on the fly based on its path and existing signatures, so the MCTS can quickly evaluate the "deletability" prior of a newly discovered path.

### Step 3: Implement MCTS Logic in `Scanner`
Replace the worker tasks and GPQ in `Scanner.scan()` with a single-threaded MCTS loop:

#### A. Selection (UCT)
Navigate from the root by picking the child $i$ that maximizes a PUCT-like score:
`Score_i = (R_i / T_i) + C * P_i * sqrt(N_parent) / (1 + N_i)`
Where $R_i$ is `total_reward`, $T_i$ is `total_time` (with a small epsilon to avoid division by zero), $N_i$ is `visits`, and $P_i$ is a prior based on `estimated_size` and signature matches.

#### B. Expansion
When reaching a leaf (unscanned directory):
-   List contents (`os.scandir` via `asyncio.to_thread` to not block UI).
-   Create child `DirectoryNode` objects.
-   Load `.gctrail` (if present) to populate `estimated_size`.
-   Calculate `heuristic_score`.

#### C. Simulation (Playout)
Perform a playout from the expanded node:
-   Measure time spent.
-   Decide whether to recurse or just sum files at the current level.
-   Calculate `Deletable Size = (Sum of File Sizes) * heuristic_score`.
-   Stop at a predefined depth or when a leaf is fully processed.

#### D. Backpropagation
Update the path back to the root:
-   Increment `visits`.
-   Add playout's `Deletable Size` to `total_reward`.
-   Add playout's duration to `total_time`.

### Step 4: Update Aggregation and UI
-   **Aggregator (`src/fsgc/aggregator.py`):** Update `summarize_tree` to return `estimated_size` and calculate a new `completion_ratio` based on Verified vs Estimated.
-   **Formatter (`src/fsgc/ui/formatter.py`):** Update `render_summary_tree` to display progress explicitly as `Verified Size / Estimated Total Size`. Use dim styles for nodes where verified size is much lower than estimated.

### Step 5: Integration in `__main__.py`
Modify the `scan` command:
1.  Initialize `SignatureManager` and `HeuristicEngine` before scanning.
2.  Pass the engine to `Scanner(path, engine)`.
3.  Run the async `scanner.scan()` generator, which now yields MCTS iterations.

## 5. Testing Strategy

### Unit Tests
-   **MCTS Selection:** Test the UCT formula to ensure it balances exploitation (high reward/time) and exploration, strongly favoring nodes with high priors (matching signatures).
-   **Simulation:** Verify that the reward function correctly calculates `(Verified Deletable Size / Time Spent)`.

### Integration Tests
-   **Mock Filesystem:** Create a directory structure with hidden "large garbage" folders and measure if the MCTS approach discovers them significantly faster (in fewer iterations) than the stochastic approach.
-   **Trail Integration:** Ensure `.gctrail` estimates are correctly loaded and influence the MCTS priors.

### UI Validation
-   Ensure the console UI updates smoothly without flickering, showing the transition from "Estimated" to "Verified" sizes as the MCTS explores the tree.
