from pathlib import Path

from fsgc.scanner import DirectoryNode


def test_directory_node_mcts_fields():
    node = DirectoryNode(path=Path("mock_dir"))
    assert hasattr(node, "visits")
    assert node.visits == 0
    assert hasattr(node, "total_reward")
    assert node.total_reward == 0.0
    assert hasattr(node, "confirmed_size")
    assert node.confirmed_size == 0
    assert hasattr(node, "estimated_size")
    assert node.estimated_size == 0
    assert hasattr(node, "is_fully_explored")
    assert node.is_fully_explored is False
    assert hasattr(node, "heuristic_score")
    assert node.heuristic_score == 0.0


def test_directory_node_parent_link():
    root = DirectoryNode(path=Path("root"))
    child = DirectoryNode(path=Path("root/child"))
    
    assert root.parent is None
    
    root.add_child("child", child)
    assert child.parent == root
    assert root._unexplored_children_count == 1
    
    child2 = DirectoryNode(path=Path("root/child2"))
    root.add_child("child2", child2)
    assert root._unexplored_children_count == 2
