# Implementation Plan: Stochastic Search Engine & .gctrail Caching

This plan details the transition from a linear BFS scanner to a concurrent, stochastic search engine with decentralized binary sidecar caching (`.gctrail`) for the `gc` tool.

## 1. Architectural Impact

- **Search Engine:** Completely replaces the synchronous BFS scanner with an asynchronous, queue-based engine.
- **Data Model:** `DirectoryNode` augmented with states: `UNSCANNED`, `GHOST`, `STALE`, `VERIFIED`.
- **Concurrency Model:** `asyncio` for Scouts (async probes) and `ThreadPoolExecutor` for Crawlers (exhaustive walk).
- **Caching:** Decentralized `.gctrail` binary files using Python `struct`.

## 2. Core Components

### A. Binary Trail Logic (`src/fsgc/trail.py`)
- **Format:**
    - Magic Bytes: `b'GCTR'`
    - Version: `1`
    - Timestamp: `double` (8 bytes)
    - Structural Hash: `unsigned long long` (8 bytes, `mtime` + `inode` count)
    - Aggregates: Total Size, Reconstructible Size, Noise Size (3 x `uint64`)
    - Big Fish List: Top-N files (>10MB) with Path and Size.
- **Protocol:** Snapshot -> Inode Validation -> Verify or Flag as Stale.

### B. Global Priority Queue (GPQ) (`src/fsgc/scanner.py`)
- Wraps `asyncio.PriorityQueue`.
- **Scoring Priors:**
    - Static: `~/.cache`, `~/Downloads` (High weight).
    - Contextual: `.git/`, `node_modules/` detection (Medium weight).
    - Historical: Paths from existing `.gctrail` files (Highest weight).

### C. Scouts & Crawlers (`src/fsgc/scanner.py`)
- **Scouts (Async):** Perform shallow probes, load trails as `GHOST`, and identify "Big Fish".
- **Crawlers (Threads):** Perform the deep exhaustive walk on `STALE` or unscanned branches to fill the "Missing Mass" (small files).

## 3. Step-by-Step Execution

### Phase 1: Data Structures & Binary Format
1.  Create `src/fsgc/trail.py` with the `GCTrail` binary schema.
2.  Update `DirectoryNode` in `src/fsgc/scanner.py` to support `ScanState`.
3.  Add `trail-dump` debug command to `src/fsgc/__main__.py`.

### Phase 2: The Stochastic Engine
1.  Implement the `GPQ` scoring and prioritization logic.
2.  Implement the `Scout` async worker routine.
3.  Implement the `Crawler` threaded worker routine.
4.  Refactor `Scanner.scan()` into an async generator yielding tree snapshots.

### Phase 3: UI & CLI Refinement
1.  Update `src/fsgc/__main__.py` to use `asyncio.run()` and `rich.live.Live`.
2.  Update `src/fsgc/ui/formatter.py` to visually distinguish `GHOST`, `STALE`, and `VERIFIED` states (e.g., using ghost 👻 and warning ⚠️ emojis).

### Phase 4: Persistence & Validation
1.  Implement the post-scan persistence hook to write/update `.gctrail` files in high-value directories.
2.  Conduct performance benchmarking: Verify O(1) startup on warm caches.

## 4. Testing Strategy
- **Unit Tests:** `struct` packing/unpacking accuracy.
- **State Transition Tests:** Assert `touch`ing a file transitions state from `VERIFIED` to `STALE`.
- **Integration Tests:** End-to-end run on large dummy structures ensuring background convergence.
- **CLI Tests:** Verify `trail-dump` output formatting.
