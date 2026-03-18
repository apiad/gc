# Execution Plan: Graceful Interruption of Scanning Phase

## Objective
Implement a feature to gracefully interrupt the scanning phase in `fsgc` by pressing `Ctrl+C` (`KeyboardInterrupt`), transitioning seamlessly to the cleanup/summary phase with whatever garbage was identified so far. The graceful interruption should only occur if the scan has met a minimum progress threshold (i.e., at least basic initialization or one full scan iteration); otherwise, it should exit the program entirely.

## Architectural Impact
The current architecture in `src/fsgc/scanner.py` utilizes an MCTS (Monte Carlo Tree Search) algorithm and yields snapshots of the mutable `DirectoryNode` root back to `src/fsgc/__main__.py`. The `__main__.py` loop consumes these snapshots to render the UI tree. 
Presently, a `KeyboardInterrupt` is caught in `__main__.py`, an error message is printed, and the program proceeds to cleanup. To meet the new requirements, we just need to refine how this exception is handled in the `run_scan` function:
- **Minimum Progress Check**: We will use the `root_node` variable (initially `None`) as our progress sentinel. Since `scanner.scan()` yields its first snapshot only after expanding the initial directory and completing its first MCTS iteration, an unpopulated `root_node` implies the minimum progress hasn't been met.
- **Graceful Transition**: If `root_node` is populated, we will display the requested visual message and ensure the node's metadata is explicitly recalculated so that any partial MCTS iterations completed before the interrupt are accurately accounted for during the cleanup/summary phase.
The change is highly localized to the CLI entry point (`__main__.py`) and gracefully integrates with the existing Phase 3 (Scoring) and Phase 4 (Aggregation) logic, which already naturally handle partially explored trees.

## File Operations
- **Modified**: `src/fsgc/__main__.py`

## Step-by-Step Execution

**Step 1: Locate `run_scan` in `src/fsgc/__main__.py`**
Find the `run_scan()` async inner function inside `_do_scan()`. This function encompasses the `Live` context manager and the `async for snapshot in scanner.scan():` loop.

**Step 2: Update the `KeyboardInterrupt` Exception Handler**
Modify the existing `except KeyboardInterrupt:` block to introduce the minimum progress check and the new visual message:
```python
        except KeyboardInterrupt:
            if not root_node:
                # Minimum progress (basic initialization / 1st iteration) not achieved.
                # Re-raise to exit the program entirely.
                raise
            console.print("\n[bold yellow]Scan interrupted. Proceeding to cleanup...[/]\n")
```

**Step 3: Synchronize Node Metadata Before Cleanup**
Because the `KeyboardInterrupt` can break the async event loop immediately after an MCTS iteration modifies the tree (but before the `scanner.scan()` generator yields and updates metadata), ensure the latest size metrics are synchronized before passing the tree to the summary phase. Add a call to `calculate_metadata()` right before returning:
```python
        if root_node:
            root_node.calculate_metadata()

        return root_node
```

## Testing Strategy
1. **Manual Validation (Early Exit)**:
   - Run `fsgc scan` and immediately press `Ctrl+C` (within milliseconds). 
   - **Expected**: The script should raise the `KeyboardInterrupt` traceback and exit the program entirely without displaying the proposal or cleanup prompts.
2. **Manual Validation (Graceful Interrupt)**:
   - Run `fsgc scan` on a large folder (e.g., the home directory `~`).
   - Let the live UI tree populate for at least 1-2 seconds, then press `Ctrl+C`.
   - **Expected**: The UI should stop updating, the message `[bold yellow]Scan interrupted. Proceeding to cleanup...[/]` should appear, and the application should transition seamlessly to the "Garbage Collection Proposal" phase, proposing deletions based on the scanned subset.
3. **Unit Test Coverage**:
   - Add a test case in `tests/test_scanner.py` that runs the `Scanner` inside an `asyncio.Task` and sends a `KeyboardInterrupt` after yielding one item. Verify that `calculate_metadata()` accurately reflects the partially scanned state and the root node is preserved.