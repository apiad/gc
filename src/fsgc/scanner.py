import asyncio
import logging
import math
import os
import random
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from fsgc.trail import BigFish, GCTrail

logger = logging.getLogger(__name__)


class ScanState(Enum):
    """
    The scanning state of a directory node.
    """

    UNVERIFIED = auto()  # Not yet scanned or currently unverified
    EXPLORING = auto()  # Currently being descended in an MCTS iteration
    GHOST = auto()  # Initialized from trail data, but not yet verified on disk
    STALE = auto()  # Verified to exist, but mtime or structure has changed since trail
    VERIFIED = auto()  # Verified on disk AND entire subtree is fully explored


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
    state: ScanState = ScanState.UNVERIFIED
    big_fish: list[BigFish] = field(default_factory=list)
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

    def __init__(self, root: Path, stay_on_mount: bool = True, engine: "Any" = None) -> None:
        self.root = root.resolve()
        self.stay_on_mount = stay_on_mount
        self.root_dev = self._get_dev(self.root)
        self.tree: DirectoryNode | None = None
        self.visited: set[str] = set()
        self.path_to_node: dict[Path, DirectoryNode] = {}
        self.engine = engine

    def _get_dev(self, path: Path) -> int:
        try:
            return os.stat(path).st_dev
        except (PermissionError, FileNotFoundError):
            return -1

    def select_node(self, node: DirectoryNode) -> DirectoryNode | None:
        """
        Select the best child node using a PUCT-like formula.
        1. Prioritize nodes with 0 visits.
        2. Score = (R/T) + C * P * sqrt(N_parent) / (1 + N)
        """
        if not node.children:
            return None

        # Filter out fully explored children
        available_children = [c for c in node.children.values() if not c.is_fully_explored]
        if not available_children:
            node.is_fully_explored = True
            return None

        # 1. Prioritize unvisited nodes
        for child in available_children:
            if child.visits == 0:
                return child

        best_score = -float("inf")
        best_child = None

        # Hyperparameter C (exploration constant)
        c = 1.414

        for child in available_children:
            # Exploitation: Efficiency (Reward / Time)
            # Add small epsilon to time to avoid division by zero
            exploitation = child.total_reward / (child.total_time + 1e-6)

            # Prior P: Combined estimated size and heuristic score
            # Normalize estimated_size (could be huge, so maybe log it or use relative to parent)
            p = (child.heuristic_score + 0.1) * (math.log10(max(1, child.estimated_size)) + 1)

            # Exploration: UCT term
            exploration = c * p * math.sqrt(node.visits) / (1 + child.visits)

            score = exploitation + exploration

            if score > best_score:
                best_score = score
                best_child = child

        return best_child or list(node.children.values())[0]

    async def mcts_iteration(self, root: DirectoryNode, signatures: list[Any]) -> None:
        """
        Perform one MCTS iteration: a complete playout from root to leaf.
        """
        start_time = time.time()
        path = [root]
        current = root

        # Save original states to revert after exploration
        original_states = {root: root.state}

        while True:
            # 1. Verification (Expansion if needed)
            if not current.is_processed:
                await self._process_directory(current)
                # After processing, load heuristics and priors
                if self.engine:
                    sig = self.engine.get_matching_signature_by_path(current.path, signatures)
                    score = self.engine.calculate_score(current, sig) if sig else 0.1
                    current.heuristic_score = score
                else:
                    current.heuristic_score = 0.1
            
            # Mark as exploring
            if current.state != ScanState.VERIFIED:
                current.state = ScanState.EXPLORING

            # 2. Termination Check
            if not current.children or current.is_fully_explored:
                break

            # 3. Selection (Move deeper)
            next_node = self.select_node(current)
            if next_node is None or next_node == current:
                break

            current = next_node
            path.append(current)
            original_states[current] = current.state

        # 4. Reward Calculation (Simulation)
        reward = await self._calculate_path_reward(path)
        iteration_time = time.time() - start_time

        # 5. Backpropagation
        for node in path:
            node.visits += 1
            node.total_reward += reward
            node.total_time += iteration_time
            
            # Revert from EXPLORING to original or STALE if not yet VERIFIED
            if node.state == ScanState.EXPLORING:
                orig = original_states.get(node, ScanState.UNVERIFIED)
                node.state = orig if orig != ScanState.EXPLORING else ScanState.UNVERIFIED

    async def _calculate_path_reward(self, path: list[DirectoryNode]) -> float:
        """
        Calculate total reward for the given path.
        """
        # Reward is the sum of (files_size * heuristic_score) for all nodes in the path
        # which have been verified.
        total_reward = 0.0
        for node in path:
            if node.is_processed:
                total_reward += node.files_size * node.heuristic_score
        return total_reward

    async def _simulate(self, node: DirectoryNode, signatures: list[Any]) -> float:
        """
        Simulate a random playout from the current node to a leaf.
        Reward is the 'Verified Deletable Size'.
        """
        # If already verified, reward is based on known size and score
        if node.is_processed:
            reward = node.files_size * node.heuristic_score
            # Recurse with some probability or until leaf?
            # Simplified: just return current node reward for now or one random child
            if node.children:
                child = random.choice(list(node.children.values()))  # noqa: S311
                reward += await self._simulate(child, signatures)
            return reward

        return 0.0

    async def scan(
        self, signatures: list[Any], num_iterations: int = 1000000
    ) -> AsyncGenerator[DirectoryNode, None]:
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
        while not root_node.is_fully_explored and iteration < num_iterations:
            await self.mcts_iteration(root_node, signatures)

            # Yield snapshot frequently
            if iteration % 10 == 0:
                self.calculate_metadata(root_node)
                yield root_node
                await asyncio.sleep(0.001)

            iteration += 1

        self.calculate_metadata(root_node)
        yield root_node

    async def _process_directory(self, node: DirectoryNode) -> None:
        """
        Scan a single directory level and update node metadata.
        """
        try:
            # 1. Trail Logic (Fast-path if hash matches)
            trail_path = node.path / ".gctrail"
            if await asyncio.to_thread(trail_path.exists):
                try:
                    data = await asyncio.to_thread(trail_path.read_bytes)
                    trail = GCTrail.from_bytes(data)
                    node.cached_size = trail.total_size
                    node.cached_hash = trail.structural_hash
                    node.big_fish = trail.big_fish
                    node.estimated_size = trail.total_size
                    # Check for quick verification
                    dir_stat = await asyncio.to_thread(os.stat, node.path)
                    entries_count = len(os.listdir(node.path))
                    current_hash = GCTrail.calculate_structural_hash(
                        dir_stat.st_mtime, entries_count
                    )
                    if current_hash == node.cached_hash:
                        # Even if hash matches, we don't set is_fully_explored here
                        # to ensure the MCTS actually visits subdirectories.
                        node.state = ScanState.VERIFIED
                        node.size = trail.total_size
                    else:
                        node.state = ScanState.STALE
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

                        if stat.st_size > 10 * 1024 * 1024:
                            node.big_fish.append(BigFish(filename=entry_name, size=stat.st_size))

            node.big_fish.sort(key=lambda x: x.size, reverse=True)
            node.big_fish = node.big_fish[:10]

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
        # Confirmed size is files in this dir + confirmed sizes of children
        confirmed_size = node.files_size
        
        # Estimated size starts with confirmed size, then adds estimates for unexplored branches
        estimated_size = node.files_size
        
        max_atime = node.atime
        max_mtime = node.mtime
        
        # A node is fully explored ONLY if it is processed AND all its children are fully explored
        all_children_fully_explored = node.is_processed

        total_ratio = 1.0 if node.is_processed else 0.0

        for child in node.children.values():
            c_size, c_atime, c_mtime, c_complete, c_ratio = self.calculate_metadata(child)
            
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
        node.confirmed_size = confirmed_size
        node.size = confirmed_size # For UI compatibility
        
        # Estimated size uses cache as a fallback if we haven't explored much
        node.estimated_size = max(estimated_size, node.cached_size)
        
        node.atime = max_atime
        node.mtime = max_mtime

        # Completion ratio: average of self + all discovered children
        items_count = len(node.children) + 1
        node.completion_ratio = total_ratio / items_count

        if all_children_fully_explored:
            node.is_fully_explored = True
            node.state = ScanState.VERIFIED

        return node.confirmed_size, node.atime, node.mtime, node.is_fully_explored, node.completion_ratio

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
