import pytest
from pathlib import Path
from fsgc.scanner import DirectoryNode, Scanner

def test_mcts_selection_prioritizes_unvisited():
    scanner = Scanner(Path("/tmp"))
    root = DirectoryNode(path=Path("/tmp"))
    
    child1 = DirectoryNode(path=Path("/tmp/1"))
    child2 = DirectoryNode(path=Path("/tmp/2"))
    
    root.add_child("1", child1)
    root.add_child("2", child2)
    
    # child1 has visits, child2 has none
    child1.visits = 1
    child2.visits = 0
    
    selected = scanner.select_node(root)
    assert selected == child2

def test_mcts_selection_uses_uct():
    scanner = Scanner(Path("/tmp"))
    root = DirectoryNode(path=Path("/tmp"))
    root.visits = 10
    
    child1 = DirectoryNode(path=Path("/tmp/1"))
    child2 = DirectoryNode(path=Path("/tmp/2"))
    
    root.add_child("1", child1)
    root.add_child("2", child2)
    
    # Both have visits, so UCT will be used
    child1.visits = 5
    child1.total_reward = 100
    child1.total_time = 1.0
    
    child2.visits = 5
    child2.total_reward = 10  # Lower reward
    child2.total_time = 1.0
    
    selected = scanner.select_node(root)
    assert selected == child1
