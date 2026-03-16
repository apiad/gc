To implement the "Incremental Refinement" scanning animation, we need to transition from a binary "use cache or scan" approach to a tiered verification system. The scanner will now use `.gctrail` data as a placeholder while concurrently verifying the directory structure's integrity. If verification succeeds (Fast-path), we trust the cache; otherwise, we incrementally refine the estimate with actual data.

### Objective
Implement a tiered scanning logic that provides immediate visual feedback using cached estimates (`GCTrail`), performs fast-path structural verification (O(1)), and gracefully falls back to incremental scanning for stale subtrees, ensuring the UI "converges" from estimated to actual sizes.

### Architectural Impact
- **State Management**: `DirectoryNode` will now distinguish between cached data (`cached_size`) and measured data (`files_size` + children).
- **Scanner Logic**: The `_worker` and `_process_directory` methods will be updated to handle the `GHOST` -> `VERIFIED` (fast-path) or `GHOST` -> `STALE` (refining) transitions.
- **Aggregation**: `calculate_metadata` will implement the reconciliation logic, using cached placeholders for `STALE` nodes until they are fully scanned.
- **UI**: The formatter will provide visual cues (e.g., "[REFINE]", dim colors) to indicate the status of the data being displayed.

### File Operations

#### 1. `src/fsgc/trail.py`
- **Modify**: Update `calculate_structural_hash` to use a stable hashing algorithm (e.g., `hashlib.blake2b` or `zlib.crc32`) instead of Python's built-in `hash()`, which is randomized across process restarts.

#### 2. `src/fsgc/scanner.py`
- **Modify `DirectoryNode`**: Add `cached_size`, `cached_hash`, and `is_processed` (bool) fields.
- **Modify `Scanner._worker`**:
    - Update trail loading to set `node.cached_size`, `node.cached_hash`, and `node.state = ScanState.GHOST`.
    - Do NOT skip the directory scan; allow the worker to proceed to `_process_directory` for verification.
- **Modify `Scanner._process_directory`**:
    - Obtain the directory's `st_mtime` and entry count.
    - Calculate the current structural hash.
    - If `node.state == ScanState.GHOST`:
        - If hashes match: Set `node.state = ScanState.VERIFIED` and skip adding children to the priority queue (Fast-path).
        - If hashes mismatch: Set `node.state = ScanState.STALE` and proceed to add children to the priority queue for incremental scanning.
    - Mark the node as `is_processed = True` at the end of the method.
- **Modify `Scanner.calculate_metadata`**:
    - Update the signature to return `(size, atime, mtime, is_complete)`.
    - Implement reconciliation logic:
        - If `VERIFIED` (and has `cached_size`): Trust `cached_size` immediately.
        - If `STALE`: Return `max(actual_size, cached_size)` and `is_complete=False` until all children are complete.
        - Once a `STALE` node and all its children are finished, transition the size to `actual_size`.
- **Modify `Scanner.persist_trails`**: Ensure it uses the same stable structural hash logic.

#### 3. `src/fsgc/aggregator.py`
- **Modify `summarize_tree`**: Include the `node.state` in the generated summary dictionary so the UI can use it for styling.

#### 4. `src/fsgc/ui/formatter.py`
- **Modify `render_summary_tree`**:
    - Add visual indicators for states:
        - `GHOST`: Dim style for labels/sizes.
        - `STALE`: Yellow style or a `[REFINE]` tag next to the name.
        - `VERIFIED`: Default or bold style.

### Step-by-Step Execution

1. **Step 1: Stable Hashing Implementation**
   - Update `GCTrail.calculate_structural_hash` in `src/fsgc/trail.py` to use `hashlib.blake2b` on a packed representation of `(mtime, entry_count)`.

2. **Step 2: Enhanced Metadata Tracking**
   - Update `DirectoryNode` in `src/fsgc/scanner.py` to store `cached_size`, `cached_hash`, and `is_processed`.

3. **Step 3: Fast-path and Stale Detection**
   - Update `Scanner._worker` to initialize `GHOST` nodes from trails.
   - Update `Scanner._process_directory` to perform the structural hash comparison.
   - Implement the branch-off: `VERIFIED` (skip children) vs `STALE` (crawl children).

4. **Step 4: Convergence Logic**
   - Update `Scanner.calculate_metadata` to handle the `max(actual, cached)` refinement logic.
   - Ensure the `is_complete` flag propagates bottom-up so parents know when to stop using stale placeholders.

5. **Step 5: Visual Feedback**
   - Update `aggregator.py` to pass state data.
   - Update `ui/formatter.py` to style `STALE` and `GHOST` nodes differently, providing the "animation" effect as nodes transition from `GHOST` -> `STALE` -> `VERIFIED`.

### Testing Strategy
- **Unit Tests**:
    - Validate that `calculate_structural_hash` returns the same value for the same inputs across multiple runs.
    - Mock `os.stat` and `os.scandir` to verify that `_process_directory` correctly identifies `VERIFIED` vs `STALE` states.
    - Test `calculate_metadata` with a mock tree containing mixed states to ensure sizes converge correctly.
- **Integration Tests**:
    - Run the scanner on a directory with an existing `.gctrail`, modify one file, and verify that the specific subtree is marked `STALE` and eventually updates its size, while other subtrees stay `VERIFIED`.
- **UI Verification**:
    - Manually verify that `STALE` nodes appear with the intended styling and that the "Refinement" animation is smooth and non-flickering.

### Final Result
The system will now provide a "best of both worlds" experience: the speed of cached results with the accuracy of a full scan, visualized through a dynamic, refining TUI.
