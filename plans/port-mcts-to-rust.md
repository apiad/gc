# Implementation Plan: Port MCTS Scanner Engine to Rust

## Objective
Develop a high-performance, multi-threaded Rust component (`fsgc-scanner-rs`) for the core MCTS scanning logic. This component will run as a standalone executable, communicating with the Python CLI via JSON lines streamed to stdout. Python will retain responsibility for argument parsing, subprocess management, TUI rendering (using Rich), final heuristic scoring, and interactive deletion decisions. The Rust component will execute the MCTS scan, process signatures provided by Python, and stream intermediate scan snapshots approximately 10 times per second. Upon cancellation or completion, Rust will return the identified garbage candidates as a JSON object. Python will manage the `.gctrail` caching.

## Architectural Impact
This initiative represents a significant architectural shift by migrating the performance-critical MCTS scanning engine from Python to a compiled Rust binary. This move aims to leverage Rust's strengths in memory safety, speed, and concurrency.

Key impacts include:
1.  **Decoupling:** The core scanning logic will be disentangled from the Python application, allowing for independent development and optimization.
2.  **Performance Enhancement:** Expect substantial improvements in scanning speed and resource utilization due to Rust's native performance and efficient concurrency primitives.
3.  **Inter-Process Communication (IPC):** A new IPC mechanism using JSON-delimited lines over standard output will be established between the Python CLI and the Rust scanner.
4.  **Python CLI Evolution:** The Python CLI will transition from directly executing scanning functions to managing the Rust binary as a subprocess, handling its output, and orchestrating the user experience.
5.  **Build System Integration:** The project's build process (e.g., via `makefile` or `pyproject.toml`) will need to accommodate the compilation of the Rust executable.

## File Operations (Conceptual)
Given the read-only nature of this task, these are conceptual locations where modifications or new files would be introduced if implementation were to proceed.

*   **New Files/Directories:**
    *   A new Rust project directory (e.g., `fsgc-scanner-rs/` at the root level, or integrated within `src/` if managed as a sub-crate).
    *   `fsgc-scanner-rs/Cargo.toml`: Rust project manifest.
    *   `fsgc-scanner-rs/src/main.rs`: Rust executable entry point.
    *   Additional `.rs` files within `fsgc-scanner-rs/src/` for MCTS logic, filesystem interaction, communication, etc.

*   **Modified Files:**
    *   `pyproject.toml`: May require configuration for building/packaging the Rust binary.
    *   `makefile`: Could be updated to include commands for building the Rust scanner.
    *   `src/fsgc/__main__.py` (or equivalent CLI entry point): To integrate `asyncio.create_subprocess_exec`, stdout/stderr capture, and signal sending to the Rust process.
    *   Python code responsible for TUI updates (e.g., within `src/fsgc/ui/`): To parse incoming JSON lines and update the Rich-based display.
    *   Python code related to the `HeuristicEngine` or signature management: To define how signature rules are passed to the Rust scanner.

*   **Deleted Files:**
    *   No existing Python files containing core scanning logic will be deleted; their role will shift to orchestration.

## Step-by-Step Execution

### Phase 1: Rust Scanner Development (`fsgc-scanner-rs`)

*   **Step 1.1: Project Setup**
    *   Initialize a new Rust project: `cargo new fsgc-scanner-rs`.
    *   Add essential dependencies to `fsgc-scanner-rs/Cargo.toml`:
        *   `serde`, `serde_json` for JSON serialization/deserialization.
        *   `rayon` for data parallelism.
        *   `walkdir` or similar crate for efficient filesystem traversal.
        *   `nix` (or equivalent) for robust signal handling.
        *   Potentially `clap` for Rust's internal argument parsing if needed, though Python will manage primary configuration.
    *   Establish a logical directory structure within `fsgc-scanner-rs/src/` for different modules (e.g., `mcts`, `fs`, `comm`, `model`).

*   **Step 1.2: Define Communication Protocol**
    *   Define Rust structs for the data to be streamed:
        *   `ScanSnapshot`: Represents intermediate progress (e.g., scanned directories, current MCTS tree summary, identified candidates). Must implement `serde::Serialize`.
        *   `CandidateEntry`: Represents a potential garbage item. Must implement `serde::Serialize`.
        *   `FinalResult`: Contains the complete list of `CandidateEntry` upon completion/cancellation. Must implement `serde::Serialize`.
    *   Ensure these Rust structs are compatible with Python's expected JSON structures (likely using `serde` on the Python side if feasible, or well-defined JSON schemas).

*   **Step 1.3: Implement Core MCTS Logic**
    *   Translate the existing MCTS algorithm logic from Python into idiomatic Rust. This includes:
        *   Data structures for MCTS nodes, states, and actions.
        *   Implementation of the MCTS loop: Selection, Expansion, Backpropagation.
    *   Implement efficient filesystem traversal logic, aiming for performance comparable to or better than Python's `os.scandir`.

*   **Step 1.4: Implement Signature Receiving and Matching**
    *   Design and implement the mechanism for receiving signature rules from Python. Options include:
        *   Passing rules as a JSON string via command-line argument during `asyncio.create_subprocess_exec`.
        *   Piping the rules as JSON data to Rust's `stdin` upon process startup.
    *   Parse the received signature rules into efficient Rust data structures.
    *   Develop robust and performant signature matching logic against file paths.

*   **Step 1.5: Integrate Concurrency (`rayon`)**
    *   Leverage `rayon` to parallelize CPU-bound tasks such as MCTS node expansion and potentially filesystem traversal across available CPU cores.
    *   Carefully manage shared mutable state to ensure thread safety.
    *   Profile and tune parallel execution for optimal performance.

*   **Step 1.6: Implement JSON Streaming to stdout**
    *   Create a dedicated module to handle writing structured data to `stdout`.
    *   Serialize `ScanSnapshot` structs to JSON strings.
    *   Append a newline character (`
`) after each JSON object to form newline-delimited JSON.
    *   Stream these JSON lines to `stdout` at a rate of approximately 10 times per second. Ensure adequate buffering to prevent output delays.

*   **Step 1.7: Implement Cancellation and Final Output**
    *   Implement signal handling (e.g., `SIGINT`, `SIGTERM`) using `nix` or a similar crate to detect termination requests from Python.
    *   Upon receiving a signal or completing the scan, serialize the `FinalResult` (containing all identified garbage candidates) to JSON.
    *   Write this final JSON object to `stdout`.
    *   Ensure the process exits with an appropriate status code (e.g., 0 for success, non-zero for errors).

### Phase 2: Python CLI Integration

*   **Step 2.1: Modify CLI Entry Point**
    *   Update the primary Python CLI script (`src/fsgc/__main__.py` or similar) to use `asyncio.create_subprocess_exec` to launch the compiled `fsgc-scanner-rs` executable.
    *   Configure the subprocess to capture `stdout` and `stderr`.
    *   Implement the chosen method for passing signature rules and any necessary configuration to the Rust process (e.g., via command-line arguments or `stdin`).

*   **Step 2.2: Implement Asynchronous IPC Reading**
    *   Create an asynchronous task that continuously reads lines from the Rust process's `stdout`.
    *   Use a JSON parser (e.g., `json` library) to deserialize each line.
    *   Implement logic to differentiate between incoming `ScanSnapshot` objects and the final `FinalResult` JSON. This might involve a field in the JSON or by tracking whether the Rust process has terminated.

*   **Step 2.3: Integrate TUI Updates**
    *   Modify the existing Rich-based TUI rendering logic to accept parsed snapshot data.
    *   Update the TUI dynamically with information from `ScanSnapshot` objects, reflecting the scanner's progress and intermediate findings.
    *   Ensure the TUI remains responsive and updates smoothly at the expected frequency.

*   **Step 2.4: Manage Subprocess Lifecycle and Signals**
    *   Implement robust error handling for subprocess creation and management.
    *   Add functionality to send termination signals (e.g., `SIGINT`) to the Rust subprocess when the user cancels the operation (e.g., Ctrl+C).
    *   Upon the Rust process's termination (either expected completion or termination due to a signal/error), parse the final JSON output from `stdout` to retrieve the complete list of garbage candidates.

*   **Step 2.5: Integrate Python Heuristics and Caching**
    *   Pass the final list of candidates received from Rust to Python's `HeuristicEngine` for final scoring and decision-making.
    *   Ensure the `.gctrail` file management and caching logic remains entirely within the Python CLI.

### Phase 3: Error Handling and Signal Management

*   **Step 3.1: Rust Error Handling**
    *   Implement comprehensive error handling within the Rust code for filesystem operations, configuration parsing, MCTS logic, and JSON serialization.
    *   Utilize `Result` types extensively and propagate errors gracefully.
    *   Log errors to `stderr` or a dedicated log file to aid debugging.
    *   Ensure that panics are caught where possible and lead to a clean exit with an informative error message, rather than an abrupt crash.

*   **Step 3.2: Python Error Handling**
    *   Implement error handling for:
        *   `FileNotFoundError` if the Rust executable is not found.
        *   Errors during subprocess communication (e.g., `BrokenPipeError`).
        *   `JSONDecodeError` for malformed JSON received from Rust.
        *   Unexpected exit codes from the Rust process.
    *   Ensure proper cleanup of resources if the Rust subprocess encounters an error or is terminated prematurely.

*   **Step 3.3: Signal Management Refinement**
    *   Thoroughly test the end-to-end signal handling: Python sends `SIGINT`, Rust receives it, gracefully shuts down, and sends back the final results.
    *   Verify that Python correctly handles its own signals (e.g., `SIGINT`) and forwards them appropriately to the child Rust process.

### Phase 4: Testing Strategy

*   **Step 4.1: Rust Unit Tests**
    *   Write unit tests for individual Rust modules:
        *   MCTS core algorithms (selection, expansion, backpropagation).
        *   Signature matching logic with diverse rule sets.
        *   JSON serialization of `ScanSnapshot`, `CandidateEntry`, and `FinalResult`.
        *   Filesystem traversal utility functions.

*   **Step 4.2: Rust Integration Tests**
    *   Develop integration tests that execute the compiled `fsgc-scanner-rs` binary as a subprocess.
    *   Verify that the binary outputs valid newline-delimited JSON.
    *   Test signal handling by sending signals programmatically and asserting correct shutdown behavior and final output.
    *   Benchmark performance against representative directory structures.

*   **Step 4.3: Python Unit Tests**
    *   Mock `asyncio.create_subprocess_exec` to simulate the Rust process's behavior.
    *   Test the IPC reading logic for parsing valid and malformed JSON lines.
    *   Test TUI update functions using mock snapshot data.
    *   Verify the correctness of signal sending logic to the mock subprocess.

*   **Step 4.4: End-to-End Integration Tests**
    *   Execute the full Python CLI application, launching the actual compiled Rust scanner.
    *   Verify that the TUI accurately reflects the scanner's progress based on JSON snapshots.
    *   Test the complete workflow, including user-initiated cancellation (e.g., Ctrl+C), ensuring graceful shutdown and correct parsing of final results.
    *   Validate that Python's heuristics and `.gctrail` caching operate correctly with the new Rust backend.
