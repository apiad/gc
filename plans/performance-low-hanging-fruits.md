# Implementation Plan: Low-Hanging Fruit Performance Optimizations

## Objective
Enhance the performance and responsiveness of `fsgc` by optimizing resource utilization, offloading CPU-bound tasks, and decoupling the scanner from the UI update cycle.

## Architectural Impact
- **Reduced Event Loop Latency:** By scaling the default `ThreadPoolExecutor` and throttling UI updates, the event loop remains responsive for TUI rendering and signal handling.
- **Improved I/O Throughput:** More aggressive worker defaults and optimized `os.scandir` usage will significantly speed up scans on high-latency or deep filesystems.
- **Smoother UI Experience:** Throttled yielding and "latest-only" snapshot processing prevent terminal flicker and lag during rapid discovery phases.

## File Operations
- **Modify** `src/fsgc/__main__.py`:
    - Configure the default `asyncio` executor with increased `max_workers`.
    - Update the default `--workers` value in the `scan` command.
    - Implement a throttling/decoupling wrapper in the `run_scan` loop.
- **Modify** `src/fsgc/scanner.py`:
    - Refactor `_get_entries` to minimize object creation (avoid redundant `Path` objects).
    - Optimize `_process_directory` to use `stat` results directly and consolidate trail loading.
    - Refine `Scanner.scan` to yield snapshots at a consistent 10Hz frequency.

## Step-by-Step Execution

### Step 1: Thread Pool and Parameter Scaling
*   **Update Global Executor:** In `src/fsgc/__main__.py`, inside the `run_scan` function, set the default executor to a new `ThreadPoolExecutor` with `max_workers=64`. This ensures `asyncio.to_thread` has enough headroom for high-concurrency I/O.
*   **Increase Default Workers:** Change the default value of the `workers` parameter in the `scan` command from `8` to a dynamic value: `min(32, (os.cpu_count() or 1) * 4)`. This provides better out-of-the-box performance on multi-core systems.

### Step 2: Optimized Entry Fetching in `Scanner`
*   **Refactor `_get_entries`:** Modify this method to return a list of tuples containing raw strings and `os.stat_result` objects instead of `Path` objects.
    *   Return: `list[tuple[str, str, bool, os.stat_result | None]]` (name, path_str, is_dir, stat).
*   **Optimize `_process_directory`:**
    *   **Direct Stat Access:** Use `stat.st_dev` from the results of `_get_entries` to check `stay_on_mount`, avoiding redundant `os.stat` calls.
    *   **Lazy Path Creation:** Only create `Path` objects for directories (to initialize `DirectoryNode`) and ignore them for files.
    *   **Evidence Collection:** Use `os.path.splitext(entry_name)[1]` instead of `Path(entry_name).suffix` to avoid overhead during file evidence collection.
*   **Consolidate Trail Loading:** Wrap the trail existence check and reading into a single `asyncio.to_thread` call to prevent multiple small blocking calls from stalling the loop.

### Step 3: UI Throttling and Decoupling
*   **Consistent Yielding in `Scanner.scan()`:** Refactor the yield loop to use a monotonic clock. Instead of yielding whenever `asyncio.wait` times out, ensure snapshots are yielded at most every 100ms, regardless of how fast the scanner queue is processed.
*   **Latest-Only Updates in `__main__.py`:** Implement a wrapper (or refine the `run_scan` loop) that ensures only the most recent snapshot is processed if multiple updates are queued. This prevents the UI from lagging behind the scanner when many directories are discovered in a single burst.

### Step 4: Selection Offloading Verification
*   **Verify `select_node`:** Ensure `Scanner.select_node` is strictly called via `asyncio.to_thread`. Since it iterates over potentially thousands of child nodes to evaluate heuristics, it must remain off the main event loop thread.

## Testing Strategy

### 1. Functional Verification
- Run `pytest` to ensure that optimizations to `_get_entries` and `_process_directory` do not break metadata aggregation or signature matching.
- Verify that `--workers` defaults to the expected value on the current machine using `fsgc scan --help`.

### 2. Performance Benchmarking
- Compare scan times on a large directory before and after changes.
- Measure the "UI Lag" by checking if the TUI remains responsive to `Ctrl+C` even during high-velocity scanning.

### 3. Concurrency Stress Test
- Run a scan with `--workers 128` to verify that the increased `max_workers` in the default executor handles the load correctly.

### 4. Regression Check
- Verify that `fsgc inspect` still works correctly, ensuring the changes to trail loading logic are backward compatible.
