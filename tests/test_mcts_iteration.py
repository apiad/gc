import pytest

from fsgc.scanner import DirectoryNode, Scanner, ScanState


@pytest.mark.asyncio
async def test_mcts_iteration(tmp_path):
    # Setup structure
    # tmp_path/
    #   dir1/
    #     file1 (1MB)
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    (dir1 / "file1").write_bytes(b"x" * 1024 * 1024)

    scanner = Scanner(tmp_path)
    root_node = DirectoryNode(path=tmp_path)
    scanner.tree = root_node
    scanner.path_to_node[tmp_path] = root_node

    # Run one iteration
    # It should expand root, create dir1_node, and simulate dir1
    await scanner.mcts_iteration(root_node)

    assert "dir1" in root_node.children
    dir1_node = root_node.children["dir1"]
    assert dir1_node.is_processed
    assert dir1_node.state == ScanState.FINISHED

    # Root stats should also be updated
    root_node.calculate_metadata()
    assert root_node.size == dir1_node.files_size
