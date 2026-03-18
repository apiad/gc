# Executive Report: High-Performance Python & Rust Integration

## Executive Summary
This report identifies four key pillars for transforming the `fsgc` filesystem garbage collector into an ultra-fast, responsive tool: **Concurrency Optimization**, **Advanced Persistence**, **Rust Extensions**, and **TUI Architecture**.

1. **Concurrency:** Properly scaling the global `ThreadPoolExecutor` (exceeding default limits) is the optimal strategy for I/O-bound filesystem tasks in Python.
2. **Persistence:** Moving from custom binary trails to a high-performance memory-mapped database like **LMDB** or a write-optimized store like **RocksDB** can significantly reduce metadata overhead.
3. **Rust Extensions:** Converting high-frequency hotspots (MCTS iterations, signature matching, and recursive aggregation) to Rust via **PyO3** and **Maturin** offers 50-100x speedups, provided the **GIL** is released during heavy computation.
4. **TUI Architecture:** A producer-consumer model using **Asyncio Queues** and **throttled UI updates** (10-15 Hz) ensures terminal responsiveness even during high-throughput scanning.

## Research Question 1: Optimizing Python's Async and Threading
- **1.1:** Optimal configuration for `ThreadPoolExecutor` and `asyncio.to_thread`.
- **1.2:** Comparative analysis of `scandir` vs. alternative I/O libraries.
- **1.3:** Event Loop lag avoidance during heavy computation.
- **1.4:** Multiprocessing vs. threading for metadata aggregation.

### Findings Overview
- **Thread Pool Scaling:** `asyncio.to_thread` uses a global executor (default: `min(32, cpu+4)`). For high-concurrency I/O like filesystem scanning, this should be increased using `loop.set_default_executor(ThreadPoolExecutor(max_workers=...))`.
- **I/O Efficiency:** `os.scandir` is highly optimized for metadata. Wrapping it in per-call async wrappers (like `aiopath`) often adds more overhead than it saves. Using `asyncio.to_thread` to run batch directory scans is the most efficient pattern.
- **Lag Prevention:** For CPU-bound MCTS calculations, offloading to a `ProcessPoolExecutor` is necessary to prevent blocking the event loop's TUI updates.
- **Aggregation Choice:** Threading is generally superior for metadata aggregation because many filesystem operations release the GIL, and it avoids the high IPC/serialization overhead of `multiprocessing` for thousands of small records.

**Detailed Report:** [research/performance-optimization/rq1_async_threading.md](performance-optimization/rq1_async_threading.md)

## Research Question 2: Advanced Caching and Persistence Strategies
- **2.1:** Performance of in-memory, binary, and embedded databases.
- **2.2:** Incremental update strategies and invalidation heuristics.
- **2.3:** Data compression techniques for metadata caches.
- **2.4:** Probabilistic structures (Bloom filters) for rapid checks.

### Findings Overview
- **Persistence Choice:** LMDB is the highest-performing option for read-heavy metadata tasks due to its memory-mapped zero-copy architecture. RocksDB is superior for massive, write-heavy updates and native compression.
- **Update Heuristics:** Recursive mtime propagation and directory-level hashing (Merkle-style) are effective for skipping large subtrees. Cuckoo filters are recommended over Bloom filters for "dirty" checks because they support item deletion.
- **Compression:** LZ4 provides the best real-time caching performance, while Zstd is ideal for persistent storage, significantly reducing I/O and increasing cache density.
- **Cache Pollution:** TinyLFU (via Count-Min Sketch) prevents the "one-hit-wonder" problem where a single large scan displaces frequently used metadata.

**Detailed Report:** [research/performance-optimization/rq2_caching.md](performance-optimization/rq2_caching.md)

## Research Question 3: Rust Integration for Hotspots
- **3.1:** Identifying hotspots for Rust conversion.
- **3.2:** PyO3 and Maturin: Best practices for integration.
- **3.3:** Zero-copy data sharing between Python and Rust.
- **3.4:** GIL release strategies in Rust.

### Findings Overview
- **Rust Hotspots:** MCTS simulations and recursive aggregation can see 50-100x speedups in Rust due to compact memory layouts and parallel execution. Signature matching should use Rust's `RegexSet` or `Hyperscan` (via `vectorscan`) for single-pass matching across thousands of patterns.
- **PyO3 & Maturin Best Practices:** Adopt the Bound API (PyO3 v0.21+) for thread safety. Use a "src" project layout and the `abi3` stable ABI to minimize wheel distribution overhead.
- **Zero-Copy Sharing:** Use the Arrow PyCapsule Interface (`pyo3-arrow`) for tabular metadata and the Python Buffer Protocol (`PyBuffer`) to allow Rust to scan Python-managed memory without duplication.
- **GIL Management:** Use `py.allow_threads` to detach the GIL for any Rust task exceeding 1ms. Combine this with the `Rayon` crate for true multi-core parallelism while keeping the Python UI thread responsive.

**Detailed Report:** [research/performance-optimization/rq3_rust_integration.md](performance-optimization/rq3_rust_integration.md)

## Research Question 4: Architectural Patterns for Responsive TUI
- **4.1:** Decoupling scan engine from UI loop via message queues.
- **4.2:** Adaptive UI refresh and throttling strategies.
- **4.3:** Low-latency input handling during background tasks.
- **4.4:** UI-safe background threading in terminal applications.

### Findings Overview
- **Decoupling Architecture:** Use an Async Producer-Consumer pattern with `asyncio.Queue` for I/O tasks and thread-safe shared state (with locks) for CPU-bound tasks.
- **Adaptive UI:** Rich's `Live` display should use a throttled `refresh_per_second` (e.g., 10-20 Hz) and "Adaptive Queue Draining" to prevent UI saturation during high-volume data bursts from rapid scanning.
- **Responsiveness:** Since Typer is synchronous by default, implement signal handling (SIGINT) for immediate interruption and utilize background listener threads for non-blocking input.
- **UI-Safe Threading:** Adhere to the "Golden Rule" (main thread only for UI updates). Rich's `Live.update()` is thread-safe and should be used to bridge background worker updates to the UI.
- **Batching & Backpressure:** Batch low-level filesystem events into fewer high-level UI updates to maintain terminal throughput and apply backpressure to prevent memory exhaustion when scanning outpaces rendering.

**Detailed Report:** [research/performance-optimization/rq4_tui_responsiveness.md](performance-optimization/rq4_tui_responsiveness.md)

## Conclusions
The path to extreme performance for `fsgc` involves moving away from pure-Python recursive traversals for large-scale operations. While Python's `asyncio` and `threading` provide sufficient concurrency for mid-sized filesystems, the language's object overhead becomes the bottleneck for scanning millions of files. Integrating Rust for the core "Scan Engine" while keeping the "UI and High-Level Logic" in Python (leveraging the zero-copy Arrow interface) is the most scalable architectural direction. For caching, a structured database approach (LMDB) is superior to custom binary blobs as the project grows in complexity and metadata volume.

## Recommendations
### Immediate Actions (Next Steps)
1. **Scale Thread Pools:** Manually increase the default `asyncio` thread pool size in the main entry point to handle high-concurrency I/O more effectively.
2. **Implement UI Throttling:** Ensure the Rich `Live` display is throttled to 10-15 Hz and uses a producer-consumer queue to bridge scanner results to the UI.
3. **Migrate to LMDB:** Replace the current `GCTrail` binary persistence with an LMDB-backed key-value store for faster metadata lookups and better reliability.

### Follow-up Research
1. **Benchmark PyO3 vs. CFFI:** Conduct a focused performance study on PyO3 for the specific recursive aggregation needs of `fsgc`.
2. **Apache Arrow Prototyping:** Explore using the Arrow PyCapsule interface for transferring scan metadata between a Rust backend and Python frontend.
3. **Merkle-Tree Hashing:** Investigate using Merkle Trees for incredibly fast change detection in large directory structures.
