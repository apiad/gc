from pathlib import Path

from fsgc.aggregator import summarize_tree
from fsgc.scanner import DirectoryNode


def test_summarize_tree_basic() -> None:
    # root (100)
    #   dir1 (80)
    #   dir2 (10)
    #   root_file (10)

    root = DirectoryNode(path=Path("root"), size=100, files_size=10)
    dir1 = DirectoryNode(path=Path("dir1"), size=80, files_size=80)
    dir2 = DirectoryNode(path=Path("dir2"), size=10, files_size=10)

    root.add_child("dir1", dir1)
    root.add_child("dir2", dir2)

    # summarize with max_children=1
    summary = summarize_tree(root, max_depth=1, min_percent=0.05, max_children=1)

    assert summary["name"] == "root"
    assert summary["size"] == 100
    assert len(summary["children"]) == 2  # dir1 + Others

    assert summary["children"][0]["name"] == "dir1"
    assert summary["children"][1]["name"] == "Others"
    assert summary["children"][1]["size"] == 20  # dir2 (10) + root_file (10)


def test_summarize_tree_depth() -> None:
    # root -> d1 -> d2
    root = DirectoryNode(path=Path("root"), size=100)
    d1 = DirectoryNode(path=Path("d1"), size=100)
    d2 = DirectoryNode(path=Path("d2"), size=100)

    root.add_child("d1", d1)
    d1.add_child("d2", d2)

    # max_depth=1 should not show d2
    summary = summarize_tree(root, max_depth=1)
    assert len(summary["children"]) == 1
    assert summary["children"][0]["name"] == "d1"
    assert len(summary["children"][0]["children"]) == 0
