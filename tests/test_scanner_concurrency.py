import asyncio
import os
from pathlib import Path
import pytest
from fsgc.scanner import Scanner, DirectoryNode

@pytest.mark.asyncio
async def test_scanner_concurrency_completes_tree(tmp_path):
    # Setup mock filesystem
    root = tmp_path / "root"
    root.mkdir()
    
    # Create multiple branches to ensure work gets split into workers
    for i in range(5):
        branch = root / f"branch_{i}"
        branch.mkdir()
        for j in range(5):
            leaf = branch / f"leaf_{j}"
            leaf.mkdir()
            (leaf / "file.txt").write_text("hello")

    scanner = Scanner(root=root, max_concurrency=4)
    
    nodes = []
    async for node in scanner.scan():
        nodes.append(node)
        
    final_node = nodes[-1]
    
    assert final_node.is_fully_explored
    assert len(final_node.children) == 5
    for c in final_node.children.values():
        assert c.is_fully_explored
        assert len(c.children) == 5
