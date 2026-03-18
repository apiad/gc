from pathlib import Path

from fsgc.scanner import DirectoryNode, Scanner


def test_mcts_selection_prioritizes_larger_estimated_size():
    scanner = Scanner(Path("mock_dir"))
    root = DirectoryNode(path=Path("mock_dir"))

    child1 = DirectoryNode(path=Path("mock_dir/1"))
    child2 = DirectoryNode(path=Path("mock_dir/2"))

    root.add_child("1", child1)
    root.add_child("2", child2)

    # child2 is larger estimated_size
    child1.estimated_size = 100
    child2.estimated_size = 500

    selected = scanner.select_node(root)
    assert selected == child2


def test_mcts_selection_skips_fully_explored():
    scanner = Scanner(Path("mock_dir"))
    root = DirectoryNode(path=Path("mock_dir"))

    child1 = DirectoryNode(path=Path("mock_dir/1"))
    child2 = DirectoryNode(path=Path("mock_dir/2"))

    root.add_child("1", child1)
    root.add_child("2", child2)

    # child1 is larger but fully explored
    child1.estimated_size = 1000
    child1.is_fully_explored = True
    child2.estimated_size = 500

    selected = scanner.select_node(root)
    assert selected == child2
