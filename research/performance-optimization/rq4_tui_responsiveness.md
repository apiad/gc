# Architectural Patterns for Ultra-Responsive TUI Applications in Python

This report explores architectural strategies for maintaining high responsiveness in Python-based Terminal User Interfaces (TUIs), specifically focusing on applications that perform intensive background operations like file system scanning.

---

## 4.1 Decoupling the "Scan Engine" from the "UI Loop"

The core challenge in ultra-responsive TUIs is preventing heavy computation (like scanning 100k+ files) from blocking the UI thread, which leads to "frozen" interfaces and delayed input response.

### Architectural Patterns

#### 1. The Async Producer-Consumer Pattern (asyncio)
Using `asyncio.Queue` is the standard for modern Python TUIs (especially those using **Textual** or **prompt_toolkit**).
- **Producer:** The Scan Engine (running as a coroutine or in a thread pool) pushes "events" (found file, update progress, scan complete) into the queue.
- **Consumer:** The UI Loop waits for items in the queue and updates the screen accordingly.

```python
import asyncio
from dataclasses import dataclass

@dataclass
class ScanEvent:
    path: str
    status: str

async def scan_engine(queue: asyncio.Queue, start_path: str):
    # Simulated recursive scan
    for root, dirs, files in os.walk(start_path):
        for name in files:
            event = ScanEvent(path=os.path.join(root, name), status="found")
            await queue.put(event)
            await asyncio.sleep(0)  # Yield control to the UI loop

async def ui_loop(queue: asyncio.Queue):
    while True:
        event = await queue.get()
        # Update Rich/Textual display here
        print(f"UI Updating: {event.path}")
        queue.task_done()
```

#### 2. Thread-Safe Shared State
For CPU-bound scanning tasks (e.g., calculating hashes), a background **Thread** or **Process** is necessary to avoid GIL contention.
- **Shared State:** Use a `threading.Lock` protected dictionary or a `multiprocessing.Manager` object.
- **Signaling:** Use a `threading.Event` to allow the UI to stop the scanner instantly.

---

## 4.2 Adaptive UI Refresh Rates and Throttling

Updating the terminal is an expensive I/O operation. High-frequency updates (e.g., every file found in a scan) can saturate the terminal's bandwidth, causing visual lag.

### Strategies

#### 1. Temporal Throttling (FPS Capping)
In **Rich**, use the `refresh_per_second` parameter in the `Live` context. This decouples the speed of your data updates from the speed of the screen redraw.
- **Recommendation:** 4-10 FPS is usually sufficient for progress bars. 24-30 FPS for smooth animations. Anything above 30 FPS wastes CPU on most terminal emulators.

```python
from rich.live import Live

with Live(my_table, refresh_per_second=10) as live:
    for data in fast_producer():
        update_table(my_table, data)
        # No need to call live.refresh() - it happens 10x/sec automatically
```

#### 2. Adaptive Queue Draining
If the background engine produces updates faster than the UI can render, the UI should "drain" the queue and only render the *latest* state.
- **Logic:** Before rendering, check if more items are in the queue. If yes, process all of them and only then trigger one redraw.

```python
async def throttled_ui_loop(queue: asyncio.Queue):
    while True:
        item = await queue.get()
        # Drain the rest of the queue to catch up
        while not queue.empty():
            item = queue.get_nowait()
            queue.task_done()
        
        # Now render only the most recent 'item'
        render_ui(item)
```

---

## 4.3 Low-Latency Input Handling in Typer/Rich

**Typer** is synchronous by design, which makes it tricky to handle "live" input during a background scan.

### Techniques for Responsiveness

#### 1. Non-Blocking Input with `nodelay`
In low-level TUIs (curses), `stdscr.nodelay(True)` makes input calls return immediately. In higher-level apps, use a dedicated input listener thread.

#### 2. Signal Handling for Graceful Interruption
To ensure the UI responds instantly to `Ctrl+C` even during heavy processing:
- Use `signal.signal(signal.SIGINT, handler)`.
- The handler sets a "stop flag" that the background thread/task checks frequently.

#### 3. Using `Textual` for Hybrid Apps
If you need complex input (mouse, keyboard shortcuts) while a scan runs, wrapping the **Rich** rendering inside a **Textual** App is the most robust solution. Textual runs its own event loop and handles input asynchronously.

---

## 4.4 UI-Safe Background Threading

**The Golden Rule:** Never update the UI from any thread other than the main thread (or the thread where the UI event loop resides).

### Implementation Patterns

| Library | Pattern |
| :--- | :--- |
| **Rich** | `Live.update()` is thread-safe. You can call it from background threads, and it safely updates the reference used by the refresh thread. |
| **Textual** | Use `app.call_from_thread(callback, *args)`. This schedules a function to run in the main async event loop. |
| **General** | Use a `queue.Queue`. The background thread `.put()`s data, and the main thread `.get()`s and renders. |

### Example: UI-Safe Threading with Rich Live
```python
import threading
from rich.live import Live

class ScannerApp:
    def __init__(self):
        self.progress_data = {"files": 0}
        self.lock = threading.Lock()

    def worker(self):
        """Background thread updating data."""
        for _ in range(10000):
            with self.lock:
                self.progress_data["files"] += 1
            time.sleep(0.001)

    def run(self):
        """Main thread handling UI."""
        thread = threading.Thread(target=self.worker, daemon=True)
        thread.start()
        
        with Live(self.get_renderable(), refresh_per_second=10) as live:
            while thread.is_alive():
                live.update(self.get_renderable())
                time.sleep(0.1)

    def get_renderable(self):
        with self.lock:
            return f"Files scanned: {self.progress_data['files']}"
```

### Key Takeaways for High Performance
1.  **Batching:** If the scan finds 1,000 files in 10ms, do not send 1,000 messages to the UI. Batch them into a single "1,000 files found" update.
2.  **Backpressure:** Monitor the UI queue size. If it grows too large, signal the scanner to slow down (backpressure) to prevent memory bloat and UI lag.
3.  **Differential Rendering:** Leverage libraries like **Textual** that only redraw the parts of the screen that changed, drastically reducing the number of ANSI escape sequences sent to the terminal.
