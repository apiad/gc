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
