import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from fsgc.config import Signature
from fsgc.trail import GCTrail, TopSubdirectory

logger = logging.getLogger(__name__)


class ScanState(Enum):
    """
    The scanning state of a directory node.
    """

    NONE = auto()  # No status set
    ENQUEUED = auto()  # Not yet scanned or currently unverified
    EXPLORING = auto()  # Currently being descended in an MCTS iteration
    FINISHED = auto()  # Verified on disk AND entire subtree is fully explored


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
    state: ScanState = ScanState.NONE
    top_subdirs: list[TopSubdirectory] = field(default_factory=list)
    children: dict[str, "DirectoryNode"] = field(default_factory=dict)
    is_dir: bool = True
    # Enhanced Metadata for Incremental Scan
    cached_size: int = 0
    cached_hash: int = 0
    is_processed: bool = False
    entry_count: int = 0
    completion_ratio: float = 0.0

    # MCTS metrics
    visits: int = 0
    total_reward: float = 0.0
    total_time: float = 0.0
    confirmed_size: int = 0
    estimated_size: int = 0
    is_fully_explored: bool = False
    heuristic_score: float = 0.0

    dirty: bool = True
    _metadata: Any = None

    def __hash__(self) -> int:
        return hash(str(self.path))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DirectoryNode):
            return False
        return self.path == other.path

    def add_child(self, name: str, node: "DirectoryNode") -> None:
        self.children[name] = node

    def calculate_metadata(self) -> tuple[int, float, float, bool, float]:
        """
        Recursively calculate total size, most recent timestamps, and completion progress.
        Returns (size, atime, mtime, is_complete, completion_ratio).
        """
        if not self.dirty:
            return self._metadata

        # Confirmed size is files in this dir + confirmed sizes of children
        confirmed_size = self.files_size

        # Estimated size starts with confirmed size, then adds estimates for unexplored branches
        estimated_size = self.files_size

        max_atime = self.atime
        max_mtime = self.mtime

        # A node is fully explored ONLY if it is processed AND all its children are fully explored
        all_children_fully_explored = self.is_processed

        total_ratio = 1.0 if self.is_processed else 0.0

        for child in self.children.values():
            c_size, c_atime, c_mtime, c_complete, c_ratio = child.calculate_metadata()

            # If child is fully explored, its size is confirmed
            if c_complete:
                confirmed_size += c_size
                estimated_size += c_size
            else:
                # If not complete, use its estimated size for our estimate
                estimated_size += child.estimated_size
                # And its confirmed size for our confirmed
                confirmed_size += child.confirmed_size

            max_atime = max(max_atime, c_atime)
            max_mtime = max(max_mtime, c_mtime)
            all_children_fully_explored = all_children_fully_explored and child.is_fully_explored
            total_ratio += c_ratio

        # Update node fields
        self.confirmed_size = confirmed_size
        self.size = confirmed_size  # For UI compatibility

        # Estimated size uses cache as a fallback if we haven't explored much
        self.estimated_size = max(estimated_size, self.cached_size)

        self.atime = max_atime
        self.mtime = max_mtime

        # Completion ratio: average of self + all discovered children
        items_count = len(self.children) + 1
        self.completion_ratio = total_ratio / items_count

        if all_children_fully_explored:
            self.is_fully_explored = True
            self.state = ScanState.FINISHED

        self._metadata = (
            self.confirmed_size,
            self.atime,
            self.mtime,
            self.is_fully_explored,
            self.completion_ratio,
        )

        self.dirty = False

        return self._metadata


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

    def __init__(
        self,
        root: Path,
        stay_on_mount: bool = True,
        engine: "Any" = None,
        signatures: list[Signature] | None = None,
    ) -> None:
        self.root = root.resolve()
        self.stay_on_mount = stay_on_mount
        self.root_dev = self._get_dev(self.root)
        self.tree: DirectoryNode | None = None
        self.visited: set[str] = set()
        self.path_to_node: dict[Path, DirectoryNode] = {}
        self.engine = engine
        self.signatures = signatures or []

    def _get_dev(self, path: Path) -> int:
        try:
            return os.stat(path).st_dev
        except (PermissionError, FileNotFoundError):
            return -1

    def select_node(self, node: DirectoryNode) -> DirectoryNode | None:
        """
        Select the most promising child node using a two-tiered heuristic:
        1. Tier 1: Historical data from .gctrail (top_subdirs).
        2. Tier 2: Preconfigured folder patterns with priorities.
        Fallback: Largest current estimated_size.
        """
        # Filter out fully explored children
        available_children = [c for c in node.children.values() if not c.is_fully_explored]

        if not available_children:
            node.is_fully_explored = True
            node.state = ScanState.FINISHED
            return None

        # Tier 1: Trail Data
        if node.top_subdirs:
            # Create a lookup for children that match trail names
            trail_names = {sub.name: sub.size for sub in node.top_subdirs}
            tier1_candidates = [c for c in available_children if c.path.name in trail_names]
            if tier1_candidates:
                # Return the candidate that was historically largest
                return max(tier1_candidates, key=lambda x: trail_names.get(x.path.name, 0))

        # Tier 2: Signatures
        if self.engine and self.signatures:
            best_priority = -1.0
            best_tier2 = None
            for child in available_children:
                # Use engine to match signature
                sig = self.engine.get_matching_signature(child, self.signatures)
                if sig and sig.priority > best_priority:
                    best_priority = sig.priority
                    best_tier2 = child

            if best_tier2:
                return best_tier2

        # Fallback: Greedy largest estimated size
        best_score = -1.0
        best_child = None

        for child in available_children:
            score = child.estimated_size

            if score > best_score:
                best_score = score
                best_child = child

        return best_child or list(node.children.values())[0]

    async def mcts_iteration(self, root: DirectoryNode) -> None:
        """
        Perform one MCTS iteration: a complete playout from root to leaf.
        """
        path = [root]
        current = root

        while True:
            # 1. Verification (Expansion if needed)
            if not current.is_processed:
                await self._process_directory(current)

            # Mark as exploring
            current.state = ScanState.EXPLORING
            current.dirty = True

            # 2. Termination Check
            if not current.children or current.is_fully_explored:
                break

            # 3. Selection (Move deeper)
            next_node = self.select_node(current)
            if next_node is None or next_node == current:
                break

            current = next_node
            path.append(current)

        # 4. Backpropagation (State & Trail Persistence)
        # Recalculate metadata from bottom up to propagate FINISHED state
        for node in reversed(path):
            node.dirty = True
            is_new_finished = not node.is_fully_explored
            node.calculate_metadata()

            # If the node just became fully explored, persist its trail
            if is_new_finished and node.is_fully_explored:
                await self.persist_trail(node)

    async def scan(self) -> AsyncGenerator[DirectoryNode, None]:
        """
        Perform an informed MCTS scan of the filesystem and yield tree snapshots.
        """
        root_node = DirectoryNode(path=self.root)
        self.tree = root_node
        self.path_to_node[self.root] = root_node
        self.visited.add(os.path.realpath(self.root))

        # Initial expansion of root
        await self._process_directory(root_node)

        iteration = 0

        while not root_node.is_fully_explored:
            await self.mcts_iteration(root_node)

            # Yield snapshot frequently
            if iteration % 100 == 0:
                root_node.calculate_metadata()
                yield root_node

            iteration += 1

        root_node.calculate_metadata()
        yield root_node

    async def _process_directory(self, node: DirectoryNode) -> None:
        """
        Scan a single directory level and update node metadata.
        """
        try:
            # 1. Trail Logic (Fast-path if hash matches)
            trail_path = node.path / ".gctrail"
            if trail_path.exists():
                try:
                    data = trail_path.read_bytes()
                    trail = GCTrail.from_bytes(data)
                    node.cached_size = trail.total_size
                    node.cached_hash = trail.structural_hash
                    node.top_subdirs = trail.top_subdirs
                    node.estimated_size = trail.total_size
                    # Check for quick verification
                    os.stat(node.path)
                    len(os.listdir(node.path))
                except Exception as e:
                    logger.debug(f"Failed to load trail at {trail_path}: {e}")

            # 2. Directory Exploration
            entries = await asyncio.to_thread(self._get_entries, node.path)
            node.entry_count = len(entries)

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
                else:
                    if stat:
                        node.files_size += stat.st_size
                        node.atime = max(node.atime, stat.st_atime)
                        node.mtime = max(node.mtime, stat.st_mtime)

            node.state = ScanState.ENQUEUED
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

    async def persist_trail(self, node: DirectoryNode, threshold_mb: int = 100) -> None:
        """
        Recursively save .gctrail files for directories larger than threshold_mb.
        """
        # Only persist for verified nodes that meet the size threshold
        if node.state == ScanState.FINISHED and node.size > threshold_mb * 1024 * 1024:
            # Calculate top 10 subdirectories
            children = sorted(node.children.values(), key=lambda x: x.size, reverse=True)
            node.top_subdirs = [
                TopSubdirectory(name=child.path.name, size=child.size) for child in children[:10]
            ]

            trail = GCTrail(
                timestamp=node.mtime,
                structural_hash=GCTrail.calculate_structural_hash(node.mtime, node.entry_count),
                total_size=node.size,
                reconstructible_size=0,
                noise_size=0,
                top_subdirs=node.top_subdirs,
            )

            trail_path = node.path / ".gctrail"
            try:
                trail_path.write_bytes(trail.to_bytes())
                logger.debug(f"Persisted trail to {trail_path}")
            except (PermissionError, OSError) as e:
                logger.debug(f"Failed to persist trail to {trail_path}: {e}")
