# Research Report 3: Rust Integration for Performance-Critical Python Components

This report explores the strategic integration of Rust into the `fsgc` (File System Garbage Collector) ecosystem to resolve performance bottlenecks. By offloading CPU-intensive tasks to Rust via PyO3 and Maturin, the system can achieve near-native execution speeds while maintaining the flexibility of a Python-based CLI and configuration layer.

---

## 3.1 Identifying High-Impact Hotspots for Rust Conversion

The following components represent the most significant performance bottlenecks in the current Python implementation. These "hotspots" are characterized by high CPU utilization, frequent memory allocations, or deep recursion.

### 1. MCTS (Monte Carlo Tree Search) Iterations
*   **The Problem:** MCTS requires thousands (or millions) of iterations, each involving four phases: Selection, Expansion, Simulation, and Backpropagation. In Python, the overhead of creating and traversing thousands of `Node` objects (each being a heavy Python object) leads to severe performance degradation.
*   **Rust Advantage:** 
    *   **Memory Layout:** Rust can use compact structs or even a flat array-based tree representation, significantly reducing cache misses.
    *   **Parallelism:** Simulations (the most expensive part of MCTS) can be run in parallel across all CPU cores using `Rayon` without GIL contention.
    *   **Speed:** A typical Rust MCTS implementation can be 50x–100x faster than a pure Python equivalent.

### 2. Signature Matching (Multi-Pattern Scanning)
*   **The Problem:** Scanning the filesystem for thousands of "garbage" signatures (e.g., regexes for build artifacts, cache patterns) using Python's `re` module is slow because it usually checks signatures sequentially.
*   **Rust Advantage:**
    *   **RegexSet:** The Rust `regex` crate provides `RegexSet`, which can match multiple patterns in a single pass over the data.
    *   **Hyperscan/Vectorscan:** For extreme performance (GB/s throughput), Rust can wrap the Hyperscan library, which uses SIMD instructions to match thousands of patterns simultaneously.
    *   **Aho-Corasick:** If signatures are literal strings, the `aho-corasick` crate provides optimal multi-pattern matching.

### 3. Recursive Aggregation & Filesystem Traversal
*   **The Problem:** Aggregating metadata (e.g., calculating total size, oldest file, or "staleness" score) across a deep directory tree in Python involves significant overhead for each `os.scandir` call and recursive function invocation.
*   **Rust Advantage:**
    *   **Efficient Walking:** The `ignore` or `walkdir` crates in Rust are highly optimized, supporting parallel directory traversal and respect for `.gitignore` files.
    *   **Zero-Overhead Recursion:** Rust's stack-based recursion and efficient iteration patterns minimize the cost of processing millions of files.

---

## 3.2 PyO3 and Maturin: Industry Best Practices

For a seamless integration, the project should follow modern "Oxidized" Python standards.

### 1. Project Layout (The "Mixed" Structure)
Avoid the "flat" layout. Use a structured approach that separates concerns:
```text
fsgc/
├── pyproject.toml      # Build system (Maturin) and metadata
├── Cargo.toml          # Rust dependencies
├── src/                # Python code
│   └── fsgc/
│       ├── __init__.py
│       └── core.pyi    # Type stubs for Rust functions
├── rust/               # Rust code
│   ├── src/lib.rs
│   └── Cargo.toml
└── tests/              # Python-based testing
```

### 2. Using the `Bound` API (PyO3 v0.21+)
Modern PyO3 code should use the `Bound` API for better performance and safety.
```rust
use pyo3::prelude::*;

#[pyfunction]
fn process_data(data: Bound<'_, PyList>) -> PyResult<usize> {
    // Bound references are safer and faster than the old &PyAny
    Ok(data.len())
}
```

### 3. Build & Distribution
*   **Maturin:** Use `maturin develop` for local testing and `maturin build --release` for production.
*   **ABI3:** Build against the stable Python ABI to ensure a single binary works across multiple Python versions (e.g., 3.9 through 3.13).
    ```toml
    [dependencies.pyo3]
    features = ["abi3-py39"]
    ```

---

## 3.3 Zero-Copy Data Sharing

To avoid the `O(N)` cost of copying large file lists or metadata tables between Python and Rust, zero-copy mechanisms are essential.

### 1. Apache Arrow & PyCapsule
The gold standard for sharing structured tabular data (e.g., file paths, sizes, timestamps).
*   **Mechanism:** Both Python (via `pyarrow`) and Rust (via `arrow-rs`) point to the same memory buffer.
*   **Implementation:** Use the `pyo3-arrow` crate to implement the **PyCapsule Interface**. This allows passing an Arrow array from Python to Rust as a simple pointer "handshake."

### 2. Python Buffer Protocol (`PyBuffer`)
For raw data (e.g., file contents being scanned for signatures).
```rust
use pyo3::buffer::PyBuffer;

#[pyfunction]
fn scan_buffer(buffer: PyBuffer<u8>) -> PyResult<bool> {
    let slice: &[u8] = unsafe { 
        std::slice::from_raw_parts(buffer.buf_ptr() as *const u8, buffer.len_bytes()) 
    };
    // Perform scanning directly on Python-managed memory
    Ok(check_signatures(slice))
}
```

---

## 3.4 Strategies for Releasing the GIL

The Global Interpreter Lock (GIL) prevents Python from running multiple threads of bytecode. However, Rust can "detach" from the GIL to perform heavy work in parallel.

### 1. The `allow_threads` Pattern
For any task lasting more than ~1ms, the GIL should be released.
```rust
#[pyfunction]
fn heavy_task(py: Python<'_>, input: Vec<String>) -> PyResult<usize> {
    // 1. Extraction: GIL is held while converting Python objects to Rust types
    let data = input; 

    // 2. Execution: Release the GIL
    let result = py.allow_threads(move || {
        // Pure Rust logic here. NO Python objects allowed.
        data.iter().filter(|s| is_garbage(s)).count()
    });

    // 3. Return: GIL is automatically re-acquired to return the result
    Ok(result)
}
```

### 2. Integration with Rayon
When the GIL is released, Rust can utilize all available CPU cores. This is particularly effective for the MCTS simulation phase or scanning thousands of files.
```rust
use rayon::prelude::*;

py.allow_threads(|| {
    // This utilizes all CPU cores while Python's main thread remains responsive
    files.par_iter().map(|f| scan(f)).collect::<Vec<_>>()
})
```

### 3. Responsiveness Impact
By releasing the GIL, the Python CLI remains responsive to `Ctrl+C` (interrupts) and can update UI elements (like progress bars in `rich` or `tqdm`) while Rust performs the heavy lifting in the background.

---

## Summary of Integration Strategy

| Feature | Action | Impact |
| :--- | :--- | :--- |
| **MCTS** | Move tree logic and simulations to Rust. | 50x+ speedup in decision making. |
| **Scanning** | Use Rust `RegexSet` or `Aho-Corasick`. | Drastically reduced I/O wait times. |
| **Data** | Use `pyo3-arrow` for file metadata exchange. | Zero memory overhead for large scans. |
| **Concurrency** | Release GIL + Rayon. | Full multi-core utilization. |
