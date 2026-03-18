# Execution Plan: FSGC Scanner Concurrency & Parallelization

## Objective
Accelerate the `fsgc` scanner by introducing concurrency using a bounded worker pool and `asyncio.to_thread`. The scanner will distribute its Monte Carlo Tree Search (MCTS) exploration across multiple parallel workers using a dynamic subtree partitioning model. Blocking file system I/O and CPU-intensive heuristic scoring will be offloaded to threads, ensuring the event loop remains responsive and UI snapshots are emitted smoothly.

## Architectural Impact
1. **Concurrency Model**: The scanner transitions from a single global MCTS loop to a queue-based bounded worker pool (e.g., 4-8 concurrent workers).
2. **Subtree Partitioning**: Each parallel worker pulls a dedicated subtree (starting with top-level folders) from an `asyncio.Queue` and runs independent MCTS iterations on it. If a subtree requires excessive iterations (e.g., large user directories), the worker dynamically splits the load by enqueuing its unexplored children.
3. **Thread Offloading**: Heavy filesystem operations (directory scanning, trail parsing) and CPU-intensive logic (heuristic selections, signature matching) are pushed to threads via `asyncio.to_thread()`.
4. **Lock-Free Thread Safety**: Tree structure mutations (adding children, updating node states, and backpropagation) will strictly execute on the main event loop thread. Because workers operate on disjoint subtrees, no complex locks are needed, and the periodic UI snapshots (via `root_node.calculate_metadata()`) are immune to race conditions.

## File Operations
- **Modify**: `src/fsgc/scanner.py`
- **Modify**: `tests/test_scanner.py` (to add concurrency tests)

## Step-by-Step Execution

### Step 1: Update Configuration & Initialization
- In `src/fsgc/scanner.py`, modify `Scanner.__init__` to accept a concurrency parameter: `max_concurrency: int = 4`.
- Ensure all relevant data structures are initialized to support queue-based task management.

### Step 2: Offload CPU & I/O Bound Tasks in `_process_directory`
- Refactor the I/O parts of `_process_directory` into a purely synchronous helper function (e.g., `_read_dir_and_trail_sync`) that performs `os.scandir` and parses the `.gctrail` files.
- In `_process_directory`, await this synchronous helper using `await asyncio.to_thread(...)`.
- Once the thread returns the file entries and trail metadata to the main event loop, synchronously update the `DirectoryNode` (e.g., `node.add_child`, update timestamps, file evidence). This keeps dictionary mutation on the main thread.
- Offload the CPU-heavy signature matching process:
  ```python
  node.signature = await asyncio.to_thread(self.engine.get_matching_signature, node, self.signatures)
  ```

### Step 3: Offload MCTS Selection in `mcts_iteration`
- In `mcts_iteration`, the `select_node` function iterates over all children and calculates heuristic scores. To prevent this CPU-bound work from blocking the event loop on wide directories, wrap it:
  ```python
  next_node = await asyncio.to_thread(self.select_node, current)
  ```

### Step 4: Implement the Bounded Worker Pool & Subtree Partitioning
- Redesign the core `scan()` method to initialize an `asyncio.Queue`.
- Seed the queue with the initial top-level subdirectories: `root_node.children.values()`.
- Create an `async def worker()` function:
  - Continuously `await queue.get()`.
  - Run a bounded batch of MCTS iterations (e.g., `max_iterations = 50`):
    ```python
    while not node.is_fully_explored and iterations < max_iterations:
        await self.mcts_iteration(node)
        iterations += 1
    ```
  - If the node is still not fully explored after the batch, partition the subtree further by finding `unexplored_children = [c for c in node.children.values() if not c.is_fully_explored]`. If they exist, enqueue them. If not (rare edge case where children aren't processed yet), re-enqueue the `node`.
  - Mark `queue.task_done()`.
- Spawn `self.max_concurrency` worker tasks.

### Step 5: Redesign the Generator Yield Loop
- Replace the existing `while not root_node.is_fully_explored:` loop in `scan()` with a loop that monitors the queue completion while periodically yielding snapshots to the UI:
  ```python
  worker_tasks = [asyncio.create_task(worker()) for _ in range(self.max_concurrency)]
  queue_task = asyncio.create_task(queue.join())
  
  while not queue_task.done():
      # Wait for the queue to finish OR the yield interval to pass
      done, pending = await asyncio.wait([queue_task], timeout=yield_interval)
      if not done:
          root_node.calculate_metadata()
          yield root_node

  # Cleanup and final yield
  for w in worker_tasks:
      w.cancel()
  
  root_node.calculate_metadata()
  yield root_node
  ```

## Testing Strategy
1. **Concurrency Validation**: Create a new test in `tests/test_scanner.py` that utilizes a deep and wide mock filesystem. Assert that a `Scanner` instantiated with `max_concurrency=4` correctly explores the entire tree.
2. **Thread-Safety & Race Condition Check**: Run a stress test scanning `>1000` mocked directories. Assert no `RuntimeError` dictionary modification errors occur during `calculate_metadata()`. Because tree mutations are restricted to the main event loop, this should remain stable.
3. **Data Integrity**: Validate that when the queue task completes, `root_node.size` and `root_node.is_fully_explored` perfectly reflect the entire mock filesystem, proving that bottom-up backpropagation successfully merges the split partitions.
4. **Yield Timeliness**: Use `pytest-asyncio` time mocking to confirm that `scan()` reliably yields exactly at the defined `yield_interval` and is not blocked by slow heuristic scoring or disk I/O.