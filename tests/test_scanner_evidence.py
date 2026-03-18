from pathlib import Path

import pytest

from fsgc.scanner import DirectoryNode, Scanner


def test_directory_node_file_evidence():
    node = DirectoryNode(path=Path("/tmp/test"))
    # This should work once we add the field
    assert hasattr(node, "file_evidence")
    assert isinstance(node.file_evidence, set)

@pytest.mark.asyncio
async def test_scanner_collects_evidence(tmp_path):
    # Create a directory with some files
    test_dir = tmp_path / "project"
    test_dir.mkdir()
    (test_dir / "main.c").touch()
    (test_dir / "main.o").touch()
    (test_dir / "Makefile").touch()
    (test_dir / "sub").mkdir()
    
    scanner = Scanner(root=tmp_path)
    # We need to process the directory
    node = DirectoryNode(path=test_dir)
    await scanner._process_directory(node)
    
    assert "main.c" in node.file_evidence
    assert ".c" in node.file_evidence
    assert "main.o" in node.file_evidence
    assert ".o" in node.file_evidence
    assert "Makefile" in node.file_evidence
    # Subdirectory names should NOT be in file_evidence based on plan
    assert "sub" not in node.file_evidence
