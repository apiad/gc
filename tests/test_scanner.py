import asyncio
import os
import time
from pathlib import Path

import pytest

from fsgc.scanner import DirectoryNode, PrioritizedPath, Scanner


def test_scanner_initialization(tmp_path: Path) -> None:
    scanner = Scanner(tmp_path)
    assert scanner.root == tmp_path.resolve()
    assert scanner.stay_on_mount is True


def test_scanner_builds_tree_with_metadata(tmp_path: Path) -> None:
    # Create mock structure
    # tmp_path/
    #   file1 (100 bytes, old)
    #   dir1/
    #     file2 (200 bytes, new)

    file1 = tmp_path / "file1"
    file1.write_bytes(b"a" * 100)
    # Set an old timestamp for file1
    old_time = time.time() - 100000
    os.utime(file1, (old_time, old_time))

    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    file2 = dir1 / "file2"
    file2.write_bytes(b"b" * 200)
    # File2 has current time
    new_time = time.time()
    os.utime(file2, (new_time, new_time))

    scanner = Scanner(tmp_path)

    async def get_root():
        root = None
        async for snapshot in scanner.scan():
            root = snapshot
        return root

    root_node = asyncio.run(get_root())

    assert isinstance(root_node, DirectoryNode)
    assert root_node.size == 300

    # Check timestamps: root should have the 'new' time from file2 in dir1
    # Note: st_atime might be slightly different on some filesystems,
    # so we check if it's at least as recent as new_time (within a small margin)
    assert root_node.atime >= new_time - 1
    assert root_node.mtime >= new_time - 1

    dir1_node = root_node.children["dir1"]
    assert dir1_node.atime >= new_time - 1


@pytest.mark.asyncio
async def test_scout_routine(tmp_path: Path) -> None:
    """
    Verify that the scout routine correctly discovers subdirectories and loads trails.
    """
    from fsgc.scanner import ScanState
    from fsgc.trail import GCTrail

    # 1. Create structure
    # tmp_path/
    #   .cache/ (High priority)
    #     file1 (10MB)
    #   .gctrail (in root)
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    (cache_dir / "file1").write_bytes(b"x" * 1024)

    # 2. Create a mock trail in root
    trail = GCTrail(
        timestamp=time.time(),
        structural_hash=123,
        total_size=5000,
        reconstructible_size=1000,
        noise_size=500,
        big_fish=[],
    )
    (tmp_path / ".gctrail").write_bytes(trail.to_bytes())

    scanner = Scanner(tmp_path)
    # Seed the GPQ manually for the test
    root_node = DirectoryNode(path=tmp_path)
    scanner.tree = root_node
    scanner.path_to_node[tmp_path] = root_node
    scanner.visited.add(os.path.realpath(tmp_path))
    await scanner.gpq.put(PrioritizedPath(priority=0, path=tmp_path))

    # Run worker for one task
    # We create a task and wait for the gpq to be processed
    worker_task = asyncio.create_task(scanner._worker())
    await scanner.gpq.join()
    worker_task.cancel()
    await asyncio.gather(worker_task, return_exceptions=True)

    # Verify results
    assert root_node.state == ScanState.STALE  # Hash mismatch triggers STALE
    assert root_node.cached_size == 5000  # Loaded from trail
    assert root_node.is_processed is True
    assert ".cache" in root_node.children
    assert root_node.children[".cache"].state == ScanState.VERIFIED
