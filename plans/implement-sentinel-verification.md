# Plan: Content-Based Sentinel Verification for Signatures

This plan refines the signature matching system by requiring the presence of specific "sentinel" files or suffixes within a directory to confirm its identity (e.g., `*.jar` in a `target` folder).

## 1. Objective
- Reduce false positives for generic folder names like `build`, `bin`, or `target`.
- Enforce "evidence-based" matching where a signature only triggers if specific ecosystem artifacts are found.

## 2. Technical Strategy

### 2.1 Schema Extension (`src/fsgc/config.py`)
- **`Signature`**: Add `sentinels: list[str] = field(default_factory=list)`.
- **`SignatureManager`**: Update the `load()` method to parse the `sentinels` field from `signatures.yaml`.

### 2.2 Evidence Collection (`src/fsgc/scanner.py`)
- **`DirectoryNode`**: Add `file_evidence: set[str] = field(default_factory=set)`. This will store filenames and suffixes found during discovery.
- **`Scanner._process_directory`**:
    - During the loop over directory entries, for each file encountered:
        - Store its name in `node.file_evidence`.
        - Store its suffix (e.g., `.jar`, `.o`) in `node.file_evidence`.
    - **Re-discovery**: After `_process_directory` finishes populating `file_evidence`, re-run `self.engine.get_matching_signature(node, self.signatures)` to ensure the node has the most accurate signature based on its contents.

### 2.3 Matching Enforcement (`src/fsgc/engine.py`)
- **`HeuristicEngine.get_matching_signature`**:
    - Implement a validation step for signatures that have `sentinels` defined.
    - Use `fnmatch` to check if any element in `node.file_evidence` matches any pattern in `signature.sentinels`.
    - If no sentinel matches, the signature is rejected for that node.

### 2.4 Configuration Update (`src/fsgc/signatures.yaml`)
- Update broad signatures with relevant sentinels:
    - `Python Virtualenv` -> `["pyvenv.cfg"]`
    - `Node Dependencies` -> `["package.json", "node_modules"]` (if nested) or just suffixes.
    - `Rust Target` -> `["CACHEDIR.TAG", ".rustc_info.json"]`
    - `Build Artifacts` -> `["*.o", "*.obj", "*.a", "*.lib"]`

## 3. Implementation Phases
1.  **Phase 1: Config**: Update `Signature` model and loader.
2.  **Phase 2: Scanner**: Implement evidence collection in the discovery loop.
3.  **Phase 3: Engine**: Implement the hard-requirement sentinel check.
4.  **Phase 4: Data**: Populate `sentinels` in `signatures.yaml`.
5.  **Phase 5: Verification**: Add unit tests for sentinel matching.

## 4. Verification Plan
- **Unit Tests**: Verify that `get_matching_signature` returns `None` if sentinels are missing.
- **Integration Test**: Run a scan on a mock project with a "fake" `build/` folder (empty) and verify it is not flagged.
