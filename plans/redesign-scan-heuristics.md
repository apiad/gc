# Plan: Redesign MCTS Exploration with Two-Tiered Heuristic

This plan outlines the steps to redesign the `select_node` logic in the MCTS scanner to use a two-tiered heuristic: prioritizing top subdirectories from `.gctrail` files (Tier 1) and using preconfigured folder patterns (Tier 2).

## 1. Objective
- Enhance scanning efficiency by using historical data (Tier 1: `.gctrail`) when available.
- Guide initial exploration using domain-specific folder patterns (Tier 2: `signatures.yaml`) when historical data is missing or exhausted.
- Update the `.gctrail` format to store top subdirectories instead of large files.

## 2. Technical Architecture

### 2.1 GCTrail Redesign (`src/fsgc/trail.py`)
- **`TopSubdirectory`**: Rename `BigFish` to `TopSubdirectory`.
- **`GCTrail` Updates**:
    - Rename `big_fish` field to `top_subdirs: list[TopSubdirectory]`.
    - Increment `VERSION` to `2`.
    - Update binary (un)packing logic (`from_bytes`, `to_bytes`) to support the new field name and class.
- **Constants**: Rename `FISH_FORMAT` -> `SUBDIR_FORMAT`, `MAX_FISH` -> `MAX_SUBDIRS`.

### 2.2 Scanner Logic (`src/fsgc/scanner.py`)
- **`DirectoryNode`**: Rename `big_fish` to `top_subdirs`.
- **`Scanner` Changes**:
    - `__init__`: Accepts `signatures: list[Signature] | None = None`.
    - `_process_directory`: Load `top_subdirs` from trail and remove large-file detection logic.
    - `persist_trail`: Calculate the top 10 children (directories) by `size` and populate `node.top_subdirs` before persistence.
    - `select_node`: Implement the **Two-Tiered Heuristic**:
        1. **Tier 1 (GCTrail)**: Prioritize children found in the trail data (`node.top_subdirs`), selecting the one with the largest historical size.
        2. **Tier 2 (Signatures)**: Match remaining candidates against `self.signatures`. Prioritize children with matching signatures of higher `priority`.
        3. **Fallback**: Default to the largest current `estimated_size`.

### 2.3 UI & Configuration
- **`config/signatures.yaml`**: Update patterns and priorities (e.g., `target`, `node_modules`, `models`, `data`, `bin`).
- **`src/fsgc/__main__.py`**:
    - Pass signatures to `Scanner`.
    - Update `trail` command output from "Big Fish" to "Top Subdirectories".

## 3. Implementation Phases

1. **Phase 1: GCTrail Refactoring**: Rename classes and update serialization logic in `src/fsgc/trail.py`.
2. **Phase 2: Scanner Integration**: Update `DirectoryNode`, `Scanner.__init__`, and trail persistence logic.
3. **Phase 3: Two-Tiered Selection**: Implement the Tier 1/Tier 2 heuristic in `select_node`.
4. **Phase 4: Integration & UI**: Pass signatures to the scanner and update CLI output.
5. **Phase 5: Verification**: Update tests and add new cases for the two-tiered logic.

## 4. Verification Plan
- **Unit Tests**:
    - `tests/test_trail.py`: Verify serialization/deserialization of `top_subdirs`.
    - `tests/test_mcts_selection.py`: Verify `select_node` prioritizes trail data first, then signatures, then falls back to estimated size.
- **Integration Test**: Run a scan on a mock project and verify the scanner targets `node_modules` or known trail hotspots correctly.
