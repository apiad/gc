import asyncio
import logging
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from fsgc.trail import BigFish, GCTrail

logger = logging.getLogger(__name__)


class ScanState(Enum):
    """
    The scanning state of a directory node.
    """

    UNSCANNED = auto()  # Not yet touched by any scout or crawler
    GHOST = auto()  # Initialized from trail data, but not yet verified on disk
    STALE = auto()  # Verified to exist, but mtime or structure has changed since trail
    VERIFIED = auto()  # Verified on disk and matches trail (or freshly scanned)


@dataclass(order=True)
class PrioritizedPath:
    """
    A path with a priority score for the Global Priority Queue.
    Lower score means higher priority.
    """

    priority: int
    path: Path = field(compare=False)


@dataclass
class DirectoryNode:
    """
    A node in the directory tree that aggregates sizes and timestamps.
    """

    path: Path
    size: int = 0  # Total size (self + children)
    files_size: int = 0  # Sum of file sizes in this directory only
    atime: float = 0.0  # Most recent access time in this branch
    mtime: float = 0.0  # Most recent modification time in this branch
    state: ScanState = ScanState.UNSCANNED
    big_fish: list[BigFish] = field(default_factory=list)
    children: dict[str, "DirectoryNode"] = field(default_factory=dict)
    is_dir: bool = True
    # Enhanced Metadata for Incremental Scan
    cached_size: int = 0
    cached_hash: int = 0
    is_processed: bool = False
    entry_count: int = 0
    completion_ratio: float = 0.0

    def __hash__(self) -> int:
        return hash(str(self.path))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DirectoryNode):
            return False
        return self.path == other.path

    def add_child(self, name: str, node: "DirectoryNode") -> None:
        self.children[name] = node


class Scanner:
    """
    A stochastic scanner that uses a priority queue and async workers
    to discover high-value directories first.
    """

    # Static Priors: Lower is higher priority
    STATIC_PRIORS = {
        ".cache": 10,
        "Downloads": 20,
        "node_modules": 5,
        ".git": 50,
        "build": 15,
        "dist": 15,
        "target": 15,
        "bin": 30,
        "obj": 30,
    }

    def __init__(self, root: Path, stay_on_mount: bool = True) -> None:
        self.root = root.resolve()
        self.stay_on_mount = stay_on_mount
        self.root_dev = self._get_dev(self.root)
        self.tree: DirectoryNode | None = None
        self.gpq: asyncio.PriorityQueue[PrioritizedPath] = asyncio.PriorityQueue()
        self.visited: set[str] = set()
        self.path_to_node: dict[Path, DirectoryNode] = {}

    def _get_dev(self, path: Path) -> int:
        try:
            return os.stat(path).st_dev
        except (PermissionError, FileNotFoundError):
            return -1

    def _get_priority(self, path: Path) -> int:
        """
        Calculate the priority score for a given path.
        """
        score = 100
        if path.name in self.STATIC_PRIORS:
            score = self.STATIC_PRIORS[path.name]

        try:
            depth = len(path.relative_to(self.root).parts)
            score += depth
        except ValueError:
            pass
        return score

    async def scan(self, num_workers: int = 4) -> "asyncio.AsyncGenerator[DirectoryNode, None]":
        """
        Perform a stochastic scan of the filesystem and yield tree snapshots.
        """
        root_node = DirectoryNode(path=self.root)
        self.tree = root_node
        self.path_to_node[self.root] = root_node
        self.visited.add(os.path.realpath(self.root))

        await self.gpq.put(PrioritizedPath(priority=0, path=self.root))

        # Launch concurrent async workers
        workers = [asyncio.create_task(self._worker()) for _ in range(num_workers)]

        # Background task to wait for the queue to be fully processed
        join_task = asyncio.create_task(self.gpq.join())

        try:
            while not join_task.done():
                self.calculate_metadata(root_node)
                yield root_node
                # Wait a bit before next snapshot to avoid UI flickering
                await asyncio.sleep(0.1)

            await join_task
        finally:
            # Stop workers
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

        # Final metadata aggregation (bottom-up)
        self.calculate_metadata(root_node)
        yield root_node

    async def _worker(self) -> None:
        """
        Async worker routine: pulls from GPQ and processes directories.
        """
        try:
            while True:
                prioritized = await self.gpq.get()
                current_path = prioritized.path
                current_node = self.path_to_node.get(current_path)

                if not current_node:
                    self.gpq.task_done()
                    continue

                # 1. Trail Logic
                trail_path = current_path / ".gctrail"
                if await asyncio.to_thread(trail_path.exists):
                    try:
                        data = await asyncio.to_thread(trail_path.read_bytes)
                        trail = GCTrail.from_bytes(data)
                        current_node.cached_size = trail.total_size
                        current_node.cached_hash = trail.structural_hash
                        current_node.state = ScanState.GHOST
                        current_node.big_fish = trail.big_fish
                    except Exception as e:
                        logger.debug(f"Failed to load trail at {trail_path}: {e}")

                # 2. Directory Exploration
                await self._process_directory(current_node)

                self.gpq.task_done()
        except asyncio.CancelledError:
            pass

    async def _process_directory(self, node: DirectoryNode) -> None:
        """
        Scan a single directory level, update node metadata, and seed GPQ.
        """
        try:
            # listdir/scandir is blocking, run in thread
            entries = await asyncio.to_thread(self._get_entries, node.path)

            dir_stat = await asyncio.to_thread(os.stat, node.path)
            dir_mtime = dir_stat.st_mtime
            node.entry_count = len(entries)
            current_hash = GCTrail.calculate_structural_hash(dir_mtime, node.entry_count)

            # Fast-path verification
            if node.state == ScanState.GHOST:
                if current_hash == node.cached_hash:
                    node.state = ScanState.VERIFIED
                    node.size = node.cached_size
                    node.mtime = dir_mtime
                    node.is_processed = True
                    node.completion_ratio = 1.0
                    return  # Skip deep crawling
                else:
                    node.state = ScanState.STALE

            for entry_name, entry_path, is_dir, stat in entries:
                if self.stay_on_mount and self._get_dev(entry_path) != self.root_dev:
                    continue

                if is_dir:
                    real_path = os.path.realpath(entry_path)
                    if real_path not in self.visited:
                        self.visited.add(real_path)
                        child_node = DirectoryNode(path=entry_path)
                        node.add_child(entry_name, child_node)
                        self.path_to_node[entry_path] = child_node

                        # Push to GPQ
                        priority = self._get_priority(entry_path)
                        await self.gpq.put(PrioritizedPath(priority=priority, path=entry_path))
                else:
                    if stat:
                        node.files_size += stat.st_size
                        node.atime = max(node.atime, stat.st_atime)
                        node.mtime = max(node.mtime, stat.st_mtime)

                        # Collect Big Fish (>10MB)
                        if stat.st_size > 10 * 1024 * 1024:
                            node.big_fish.append(BigFish(filename=entry_name, size=stat.st_size))

            # Sort and limit big fish
            node.big_fish.sort(key=lambda x: x.size, reverse=True)
            node.big_fish = node.big_fish[:10]

            # Update state
            if node.state != ScanState.STALE:
                node.state = ScanState.VERIFIED

            node.is_processed = True

        except (PermissionError, FileNotFoundError) as e:
            logger.debug(f"Skipping {node.path}: {e}")

    def _get_entries(self, path: Path) -> list[tuple[str, Path, bool, os.stat_result | None]]:
        """
        Blocking call to scan a directory and return metadata for its entries.
        """
        results = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    try:
                        stat = entry.stat(follow_symlinks=False)
                        results.append((entry.name, Path(entry.path), is_dir, stat))
                    except (PermissionError, FileNotFoundError):
                        results.append((entry.name, Path(entry.path), is_dir, None))
        except (PermissionError, FileNotFoundError):
            pass
        return results

    def calculate_metadata(self, node: DirectoryNode) -> tuple[int, float, float, bool, float]:
        """
        Recursively calculate total size, most recent timestamps, and completion progress.
        Returns (size, atime, mtime, is_complete, completion_ratio).
        """
        if node.state == ScanState.VERIFIED and not node.children and node.cached_size > 0:
            # Fast-path verification (no children loaded, trust cache)
            node.size = max(node.size, node.cached_size)
            node.completion_ratio = 1.0
            return node.size, node.atime, node.mtime, True, 1.0

        total_size = node.files_size
        max_atime = node.atime
        max_mtime = node.mtime
        all_children_complete = node.is_processed

        total_ratio = 1.0 if node.is_processed else 0.0

        for child in node.children.values():
            c_size, c_atime, c_mtime, c_complete, c_ratio = self.calculate_metadata(child)
            total_size += c_size
            max_atime = max(max_atime, c_atime)
            max_mtime = max(max_mtime, c_mtime)
            all_children_complete = all_children_complete and c_complete
            total_ratio += c_ratio

        # Use cached size as placeholder while stale/ghost, unless actual is larger
        if node.state in (ScanState.STALE, ScanState.GHOST) and not all_children_complete:
            node.size = max(total_size, node.cached_size)
        else:
            node.size = total_size

        node.atime = max_atime
        node.mtime = max_mtime

        if node.state == ScanState.STALE and all_children_complete:
            node.state = ScanState.VERIFIED

        # Completion ratio: average of self + all discovered children
        items_count = len(node.children) + 1
        node.completion_ratio = total_ratio / items_count

        return node.size, node.atime, node.mtime, all_children_complete, node.completion_ratio

    async def persist_trails(self, node: DirectoryNode, threshold_mb: int = 100) -> None:
        """
        Recursively save .gctrail files for directories larger than threshold_mb.
        """
        # Only persist for verified nodes that meet the size threshold
        if node.state == ScanState.VERIFIED and node.size > threshold_mb * 1024 * 1024:
            trail = GCTrail(
                timestamp=node.mtime,
                structural_hash=GCTrail.calculate_structural_hash(node.mtime, node.entry_count),
                total_size=node.size,
                reconstructible_size=0,  # TODO: Calculate based on scores
                noise_size=node.files_size,
                big_fish=node.big_fish,
            )
            trail_path = node.path / ".gctrail"
            try:
                await asyncio.to_thread(trail_path.write_bytes, trail.to_bytes())
                logger.debug(f"Persisted trail to {trail_path}")
            except (PermissionError, OSError) as e:
                logger.debug(f"Failed to persist trail to {trail_path}: {e}")

        for child in node.children.values():
            await self.persist_trails(child, threshold_mb)
