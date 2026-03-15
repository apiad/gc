from pathlib import Path

from fsgc.scanner import DirectoryNode, Scanner


def test_scanner_initialization(tmp_path: Path) -> None:
    scanner = Scanner(tmp_path)
    assert scanner.root == tmp_path.resolve()
    assert scanner.stay_on_mount is True


def test_scanner_builds_tree(tmp_path: Path) -> None:
    # Create mock structure
    # tmp_path/
    #   file1 (100 bytes)
    #   dir1/
    #     file2 (200 bytes)

    file1 = tmp_path / "file1"
    file1.write_bytes(b"a" * 100)

    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    file2 = dir1 / "file2"
    file2.write_bytes(b"b" * 200)

    scanner = Scanner(tmp_path)
    root_node = scanner.scan()

    assert isinstance(root_node, DirectoryNode)
    assert root_node.path == tmp_path.resolve()
    assert root_node.files_size == 100
    assert "dir1" in root_node.children

    dir1_node = root_node.children["dir1"]
    assert dir1_node.files_size == 200

    # Total sizes
    assert dir1_node.size == 200
    assert root_node.size == 300
