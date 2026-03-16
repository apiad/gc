import asyncio
import os
import time
from pathlib import Path

import pytest

from fsgc.scanner import DirectoryNode, Scanner


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
        async for snapshot in scanner.scan(signatures=[]):
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
