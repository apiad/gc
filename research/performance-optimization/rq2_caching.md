# Research Question 2: Advanced Caching and Persistence Strategies for Filesystem Metadata

This report synthesizes research into high-performance caching and persistence mechanisms for filesystem metadata, focusing on performance tradeoffs, incremental update strategies, compression, and probabilistic optimization.

---

## 2.1 Performance Comparison of Storage Backends

Filesystem metadata workloads are characterized by high-frequency, small-sized operations (lookup, stat, create, delete). Choosing the right storage engine depends on the balance between read latency, write throughput, and operational complexity.

### **Backend Comparison Matrix**

| Feature | **In-Memory** | **Binary (GCTrail)** | **LMDB** | **RocksDB** | **SQLite (WAL)** |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Data Structure** | Hash Map / B-Tree | Sequential Log | B+Tree (mmap) | LSM-Tree | B-Tree |
| **Read Latency** | Ultra-low (ns) | High (Requires index) | Low (Zero-copy) | Moderate (Read Amp) | Moderate (SQL overhead) |
| **Write Throughput** | Ultra-high | High (Append-only) | Moderate (Single writer) | **Ultra-high** | Moderate |
| **Persistence** | None | Simple / Log-based | ACID (mmap) | ACID (WAL/LSM) | ACID (WAL) |
| **Concurrency** | Thread-safe (Locking) | Manual / Complex | 1 Writer / Many Readers | Many Writers / Readers | 1 Writer / Many Readers |
| **Compression** | Not native | Manual | Not native | **Native (LZ4/Zstd)** | Limited (Page-level) |

### **Deep Dive into Storage Models**

1.  **In-Memory Caching:**
    *   **Pros:** Fastest possible access; zero I/O overhead.
    *   **Cons:** Volatile (lost on crash/reboot); limited by physical RAM; high memory overhead per object (Python objects vs. packed C structs).
    *   **Strategy:** Best used as a "hot" tier for the most frequently accessed directories.

2.  **Binary Formats (GCTrail):**
    *   **Concept:** A custom, append-only binary log (similar to a write-ahead log) or a packed structure optimized for the specific metadata needed.
    *   **Pros:** "Bare metal" performance; minimal disk footprint; zero "database" overhead.
    *   **Cons:** Manual management of consistency, crash recovery, and indexing. Requires a separate indexing mechanism (e.g., in-memory hash map) to avoid $O(N)$ scans.
    *   **GCTrail Context:** Likely implements a sequential trail of file signatures and GC decisions, prioritizing write speed and auditability.

3.  **LMDB (Lightning Memory-Mapped Database):**
    *   **Architecture:** Uses a B+Tree where the entire database is memory-mapped (`mmap`) into the process address space.
    *   **Key Advantage:** Reads are **zero-copy**; the application accesses data directly from the OS page cache. It is often the fastest for random reads of metadata.
    *   **Caveat:** Single writer bottleneck; file size can only grow (fragmentation requires manual compaction).

4.  **RocksDB (LSM-Tree):**
    *   **Architecture:** Designed for SSD/NVMe. Writes are buffered in memory ("MemTables") and flushed to sorted files ("SSTables") on disk.
    *   **Key Advantage:** **LSM-trees turn random writes into sequential writes.** This makes RocksDB ideal for metadata-heavy workloads where many files are created/deleted simultaneously.
    *   **Storage Efficiency:** Native support for block-level compression (LZ4/Zstd) significantly reduces metadata footprint.

5.  **SQLite (WAL Mode):**
    *   **Architecture:** Traditional B-tree SQL engine.
    *   **Key Advantage:** Full SQL support allows complex queries (e.g., "sum file sizes grouped by extension") that are difficult in KV stores.
    *   **Tuning:** Must use `PRAGMA journal_mode=WAL` and `synchronous=NORMAL` to be competitive. Even then, the SQL parsing layer adds overhead (~35% slower than direct KV access).

---

## 2.2 Incremental Update Strategies and Invalidation Heuristics

To avoid scanning the entire filesystem ($O(N)$), a high-performance scanner must use incremental strategies.

### **1. Push vs. Pull Change Detection**
*   **Push (OS Events):** Using `inotify` (Linux), `FSEvents` (macOS), or `ReadDirectoryChangesW` (Windows).
    *   **Pros:** Real-time; low overhead.
    *   **Cons:** Event queues can overflow; requires a daemon to be active; missed events if the daemon is down.
*   **Pull (Snapshot/Journal):**
    *   **FS Snapshots:** ZFS or Btrfs diffs (`zfs diff`) provide instant delta reports between two points in time.
    *   **USN Journal (NTFS):** Reading the persistent change log directly.

### **2. Directory-Level Change Tracking (Deep Tracking)**
Standard filesystems only update a directory's `mtime` when children are added or removed, not when they are modified. To optimize deep scans:
*   **Merkle Trees (Metadata Hashing):** Each directory node stores a hash of its children's metadata. If a child changes, the parent hash is invalidated and recomputed recursively up to the root.
*   **Recursive Mtime (Propagated Mtime):** A user-space strategy where modifying a leaf file triggers an `mtime` update in every ancestor directory. This allows a scanner to skip an entire subtree if the top-level directory's `mtime` is unchanged.
*   **Directory Generation Numbers:** Some filesystems (Ceph, Lustre) maintain a counter that increments on any recursive change, providing a fast "dirty" check.

### **3. Invalidation Heuristics**
*   **Lazy Invalidation:** Mark metadata as "stale" but don't re-scan until the next access.
*   **Eager Invalidation:** Proactively update the cache on event notification.
*   **Coarse-Grained:** Invalidate the whole subtree (simple but expensive to rebuild).
*   **Fine-Grained:** Track individual inodes (efficient but memory-intensive).

---

## 2.3 Data Compression Techniques for Massive Metadata Caches

As metadata counts reach the millions, RAM and disk usage become significant. Compression can increase "cache density."

### **LZ4 vs. Zstd Comparison**

| Metric | **LZ4** | **Zstd (Levels 1-3)** |
| :--- | :--- | :--- |
| **Compression Speed** | ~500 MB/s+ | ~150 - 300 MB/s |
| **Decompression Speed** | ~2-5 GB/s (near-memory) | ~0.8 - 1.2 GB/s |
| **Compression Ratio** | 1.5x - 2.0x | **3.0x - 5.0x** |
| **Use Case** | Real-time, low-latency, NVMe | High-density, cold storage, HDD |

### **Key Insights for Metadata**
*   **Cache Density:** Using **Zstd** allows 3-5x more metadata to fit in the same RAM. If the working set is larger than RAM, Zstd can be **faster** than LZ4 because it prevents disk I/O (swapping out-of-cache metadata for CPU cycles).
*   **Early Abort:** LZ4 is superior for "uncompressible" data (e.g., encrypted filenames) as it can abort early with zero penalty.
*   **Small Block Compression:** Metadata entries are often tiny (hundreds of bytes). Both LZ4 and Zstd perform better when compressing **blocks** of metadata rather than individual records.

---

## 2.4 Probabilistic Structures for Rapid "Dirty" Checks

Probabilistic structures like **Bloom Filters** and **Cuckoo Filters** allow for extremely fast, constant-time checks to see if an item is *potentially* in a set, using minimal memory.

### **1. Bloom Filters for "Not-Dirty" Checks**
*   **The Set:** Store identifiers (Path + mtime + size) of "Clean" files.
*   **Operation:**
    1.  Hash current file metadata.
    2.  Check Bloom Filter.
    3.  **Negative Result:** File is **definitely dirty**. Proceed to scan.
    4.  **Positive Result:** File is **probably clean**. Perform a final `stat` or DB lookup to confirm (handling the false positive).
*   **Efficiency:** Uses only ~10 bits per file. 10 million files fit in ~12MB of RAM.

### **2. Cuckoo Filters for Dynamic Metadata**
*   **Why:** Standard Bloom Filters do not support deletions.
*   **Cuckoo Filter Advantage:** Allows for `delete()` operations when files are removed or modified. This is critical for long-running caches where "Clean" files become "Dirty" over time.
*   **Performance:** Slightly higher lookup cost than Bloom Filters but better space efficiency for low false-positive rates.

### **3. Admission Control (TinyLFU)**
*   **Problem:** One-hit-wonder scans (e.g., `grep -r`) pollute the metadata cache.
*   **Solution:** Use a **Count-Min Sketch** to track access frequency. Do not admit metadata into the primary cache until it has been "seen" multiple times. This ensures the cache only holds truly "hot" metadata.

---

## Summary Recommendations for RQ2

1.  **Persistence:** Use **LMDB** for read-heavy local caching due to its zero-copy mmap architecture. Use **RocksDB** if the system expects high-concurrency writes and needs built-in compression.
2.  **Incremental Scanning:** Prioritize **OS Events** (push) for real-time updates, but implement **Merkle Tree-style hashing** at the directory level to allow for extremely fast pull-based "deep checks."
3.  **Compression:** Use **LZ4** for the in-memory/hot-tier cache and **Zstd** for the persistent on-disk metadata (GCTrail).
4.  **Optimizing "Dirty" Checks:** Deploy a **Cuckoo Filter** as a front-end for the metadata cache. This allows the scanner to immediately skip files that haven't changed without hitting the database or the filesystem `stat` call.
