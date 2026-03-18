# RQ1: Optimizing Python's Async and Threading for I/O-bound Filesystem Tasks

This report details strategies for optimizing Python applications performing heavy filesystem I/O and metadata aggregation, specifically focusing on the interplay between `asyncio`, threading, and multiprocessing.

---

## 1.1 Optimal Configuration for `ThreadPoolExecutor` and `asyncio.to_thread`

### Relationship and Defaults
*   `asyncio.to_thread` (Python 3.9+) is a high-level convenience wrapper for `loop.run_in_executor(None, func, *args)`.
*   It utilizes the event loop's **default executor**, which is a `ThreadPoolExecutor`.
*   **Default Limit:** Since Python 3.8, the default `max_workers` is `min(32, os.cpu_count() + 4)`. This is often insufficient for high-concurrency I/O tasks where hundreds or thousands of concurrent requests might be pending.

### Optimization Strategies
1.  **Global Tuning:** For applications where `to_thread` is used pervasively, increase the global thread limit early in the lifecycle:
    ```python
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    async def main():
        loop = asyncio.get_running_loop()
        # Increase limit for all to_thread calls
        loop.set_default_executor(ThreadPoolExecutor(max_workers=100))
    ```
2.  **Scoped Executors:** Use dedicated pools for different I/O types (e.g., one for fast local disk access, another for slow network mounts) to prevent "slow" I/O from starving "fast" I/O.
    ```python
    network_executor = ThreadPoolExecutor(max_workers=50, thread_name_prefix="NetworkIO")
    # ... inside async function:
    await loop.run_in_executor(network_executor, sync_io_func)
    ```
3.  **ContextVars:** Always prefer `asyncio.to_thread` over manual `run_in_executor` if the application relies on `contextvars` (e.g., tracking request IDs in web frameworks), as `to_thread` automatically propagates the context.

---

## 1.2 Comparative Analysis: `scandir` vs. Alternative I/O Libraries

### `os.scandir` (The Gold Standard)
`os.scandir()` is significantly faster than `os.listdir()` or `os.walk()` because it returns `DirEntry` objects. These objects contain metadata (like `is_file`, `is_dir`) obtained during the initial directory listing syscall, avoiding thousands of subsequent `stat()` calls.

### `aiopath` and `aiofiles`
*   **Mechanism:** Both libraries are essentially wrappers that run standard synchronous I/O operations in a thread pool using `run_in_executor`.
*   **Performance Overhead:** For metadata-heavy tasks (like scanning a directory tree), the overhead of wrapping every `is_file()` or `stat()` call in an `await` (which involves thread dispatching and context switching) can outweigh the benefits.
*   **Recommendation:**
    *   **For Directory Scanning:** Use `asyncio.to_thread(os.scandir, path)` or wrap a large recursive scan in a single `to_thread` call. This performs the bulk of the "fast" metadata I/O in a single thread dispatch.
    *   **For File Content I/O:** `aiofiles` is useful for maintaining a "clean" async codebase when reading/writing file contents in a web server context, ensuring the loop never blocks for long-running disk I/O.

---

## 1.3 Strategies for Avoiding Event Loop Lag during Heavy Computation (e.g., MCTS)

Heavy computations like Monte Carlo Tree Search (MCTS) are CPU-bound and will block the `asyncio` event loop, causing "lag" or complete unresponsiveness.

### Primary Strategy: `ProcessPoolExecutor`
Offload the search logic to a separate process to bypass the Global Interpreter Lock (GIL).
```python
async def run_mcts(state):
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor() as pool:
        # Offloads CPU-intensive logic to a worker process
        result = await loop.run_in_executor(pool, heavy_search_logic, state)
    return result
```

### Advanced Parallelization: Root Parallelization
Instead of trying to share a single tree across processes (which is slow due to Pickling/IPC overhead), run multiple independent searches in different processes and aggregate results (e.g., sum visit counts) at the end.

### Cooperative Yielding
If keeping everything in one process is required, break the computation into small batches and yield control:
```python
async def iterative_mcts(state, total_iters=1000, batch_size=50):
    for _ in range(0, total_iters, batch_size):
        perform_mcts_batch(state, batch_size)
        await asyncio.sleep(0) # Yield control back to the event loop
```

---

## 1.4 Multiprocessing vs. In-thread for Metadata Aggregation

### The Comparison

| Scenario | Recommendation | Reasoning |
| :--- | :--- | :--- |
| **I/O-Bound (Local/Network)** | **Threading** | `os.scandir` and `os.stat` release the GIL. Multiple threads can wait on disk I/O efficiently. |
| **High Memory Sharing** | **Threading** | Threads share memory. Aggregating results into a single list/dict is "free." |
| **CPU-Bound Logic** | **Multiprocessing** | Best if you are performing heavy transformations (e.g., regex, deep inspection) on every file record. |
| **Millions of Records** | **Threading** | IPC/Pickling overhead for returning millions of metadata objects from child processes to the parent is often slower than the computation itself. |

### Final Recommendation for Metadata Aggregation
**Use `ThreadPoolExecutor` with a pool size of ~32.** 
*   Filesystems have physical limits on concurrency (especially mechanical HDDs). High thread counts (>100) on a single disk often lead to "thrashing" and reduced throughput.
*   For SSDs, you can scale higher, but usually, the Python interpreter becomes the bottleneck before the SSD does.
*   **Only switch to Multiprocessing** if your profiling shows that the main thread is pinned at 100% CPU purely from processing the metadata results, and not from the I/O itself.
