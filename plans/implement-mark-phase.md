# Implementation Plan: Mark Phase & Interactive Deletion

This plan outlines the steps to implement the "Mark Phase" (heuristic scoring) and an interactive TUI for suggesting and selecting "garbage" items for deletion in the `gc` tool.

## 1. Metadata Enhancement (`src/fsgc/scanner.py`)

To support the "Recency Decay" ($A(n)$) heuristic, we need to capture access and modification times during the scan.

-   **Update `DirectoryNode`:**
    -   Add `atime: float` and `mtime: float` fields.
-   **Update `Scanner.scan()`:**
    -   Extract `st_atime` and `st_mtime` from `entry.stat()` for both files and directories.
    -   For directories, `atime` and `mtime` should reflect the *maximum* (most recent) value found among their immediate children (files).

## 2. Heuristic Engine (`src/fsgc/engine.py`)

Implement the scoring logic as defined in the design document: $S(n) = w_1 \cdot P(n) + w_2 \cdot A(n) + w_3 \cdot R(n)$.

-   **`HeuristicEngine` Class:**
    -   **`score_node(node, signatures)`:**
        -   **Pattern Match ($P(n)$):** Check if `node.path` matches any pattern in `signatures.yaml` using `pathlib.Path.match`.
        -   **Recency Decay ($A(n)$):** Calculate $1 - \frac{t_{now} - t_{atime}}{t_{threshold}}$. Use a default threshold (e.g., 90 days).
        -   **Regenerability ($R(n)$):** Use the `priority` value from the matching signature.
    -   **`apply_scoring(root_node, signatures)`:** Perform a post-scan traversal to assign a score to every `DirectoryNode`.

## 3. Aggregation & Grouping (`src/fsgc/aggregator.py`)

Group scored nodes into actionable "suggestions" based on their signatures.

-   **`group_by_signature(root_node, signatures)`:**
    -   Identify all nodes with a score above a minimum threshold (e.g., 0.1).
    -   Group these nodes by the **Signature Name** (e.g., "Node Dependencies", "Python Bytecode").
    -   Calculate the **Total Size** and **Average Score** for each group.
    -   Flag groups for **Auto Pre-check** if their average score exceeds 0.8.

## 4. Interactive TUI (`src/fsgc/ui/prompt.py`)

Implement the interactive selection interface.

-   **Dependencies:** Add `InquirerPy` to `pyproject.toml`.
-   **`prompt_for_deletion(groups)`:**
    -   Use `InquirerPy.checkbox` to present the grouped suggestions.
    -   Label format: `[ ] Signature Name - Total Size (Average Score)`.
    -   Pre-select items based on the auto-check flag.
-   **Confirmation Menu:** After selection, provide options for `[Run Collection]`, `[Dry Run]`, and `[Abort]`.

## 5. Sweep Phase & CLI Integration (`src/fsgc/__main__.py`)

Connect all the phases and implement the actual deletion logic.

-   **`sweep(selected_groups, dry_run=True)`:**
    -   Iterate through all nodes in the selected groups.
    -   If `dry_run` is True, print the paths that *would* be deleted.
    -   If `dry_run` is False, use `shutil.rmtree` (or `trash-cli` if integrated) to delete the directories.
    -   Implement safety checks to prevent deleting critical paths (e.g., home directory, system folders).
-   **Update CLI Entry Point:**
    -   Scan -> Mark (Score) -> Aggregate (Group) -> Prompt -> Sweep.

## 6. Verification & Testing

-   **Unit Tests (`tests/test_engine.py`):** Verify the scoring formula with mock nodes and timestamps.
-   **Integration Test:** Create a mock directory structure with old `node_modules` and new `src` folders and verify that `gc` correctly suggests the former for deletion.

## Dependencies

-   `InquirerPy`: For interactive checkbox selection.
-   `PyYAML`: For signature loading.
