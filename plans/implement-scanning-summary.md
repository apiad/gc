# Implementation Plan: Directory Scanning & Tree Summary

This plan outlines the steps to implement a hierarchical directory size summary in the `gc` tool using `Rich` for TUI representation and `typer` for CLI configuration.

## 1. Data Structures (`src/fsgc/scanner.py`)

To aggregate sizes up the tree, we need a node-based structure that maintains parent-child relationships and total size.

-   **`DirectoryNode` Class:**
    -   `path: Path`
    -   `size: int` (self size + children size)
    -   `children: Dict[str, DirectoryNode]`
    -   `files_size: int` (sum of file sizes in this directory only)
    -   `is_dir: bool`

-   **Update `Scanner`:**
    -   Modify `Scanner.scan()` to build a `DirectoryNode` tree during its BFS/DFS traversal instead of just yielding entries.
    -   Add a `calculate_sizes()` method that recursively calculates the total size of each node from the bottom up.

## 2. Aggregation Logic (`src/fsgc/aggregator.py`)

This component will process the `DirectoryNode` tree and apply filtering for the summary.

-   **`summarize_tree(node, max_depth, min_percent, max_children)` function:**
    -   Recursive function that traverses the `DirectoryNode` tree.
    -   **Filtering Rules:**
        1.  Only descend up to `max_depth`.
        2.  For a given node, sort children by size (descending).
        3.  Keep children where `(child.size / node.size) >= min_percent`.
        4.  Keep at most `max_children` individual children.
        5.  Sum the sizes of all other children and files into a single "Others" virtual node.

## 3. TUI Rendering (`src/fsgc/ui/formatter.py`)

Use `Rich.tree` to render the filtered summary.

-   **`render_summary_tree(summary_data)` function:**
    -   Converts the aggregated summary data into a `rich.tree.Tree` object.
    -   Format each line: `[bold blue]Directory Name[/] - [green]Size[/] ([yellow]percentage%[/])`.
    -   Human-readable size formatting (e.g., `1.2 GB`).

## 4. CLI Configuration (`src/fsgc/__main__.py`)

Update the `scan` command with new options.

-   **New CLI Flags:**
    -   `--depth / -d`: Default `3` (int).
    -   `--min-percent / -p`: Default `0.05` (float, 5%).
    -   `--limit / -l`: Default `4` (int, max children to show).
-   **Orchestration:**
    1.  Initialize `Scanner`.
    2.  Build the `DirectoryNode` tree.
    3.  Call `summarize_tree` with the CLI flag values.
    4.  Pass the summary to `render_summary_tree` and print it via `Rich.console`.

## 5. Verification & Testing

-   **Unit Tests (`tests/test_aggregator.py`):**
    -   Test the filtering logic with mock `DirectoryNode` trees.
    -   Verify that "Others" is calculated correctly.
-   **Integration Test:**
    -   Run `gc scan --depth 2` on the project's own repository and verify the output structure.

## Dependencies

-   `Rich`: For tree rendering.
-   `Typer`: For CLI flags.
