from pathlib import Path

from fsgc.config import Signature
from fsgc.engine import HeuristicEngine
from fsgc.scanner import DirectoryNode, Scanner
from fsgc.trail import TopSubdirectory


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
    child1.visits = 1
    child2.visits = 1

    selected = scanner.select_node(root)
    assert selected == child2


def test_mcts_selection_tier1_trail():
    scanner = Scanner(Path("mock_dir"))
    root = DirectoryNode(path=Path("mock_dir"))

    child1 = DirectoryNode(path=Path("mock_dir/1"))
    child2 = DirectoryNode(path=Path("mock_dir/2"))
    root.add_child("1", child1)
    root.add_child("2", child2)

    # Trail says child2 was larger
    root.top_subdirs = [TopSubdirectory(name="2", size=1000)]

    selected = scanner.select_node(root)
    assert selected == child2


def test_mcts_selection_tier2_signatures():
    # Setup scanner with signatures
    sigs = [
        Signature(name="High", pattern="**/high/", priority=0.9),
        Signature(name="Low", pattern="**/low/", priority=0.1),
    ]
    engine = HeuristicEngine()
    scanner = Scanner(Path("mock_dir"), engine=engine, signatures=sigs)
    root = DirectoryNode(path=Path("mock_dir"))

    child1 = DirectoryNode(path=Path("mock_dir/low/"))
    child2 = DirectoryNode(path=Path("mock_dir/high/"))
    root.add_child("low", child1)
    root.add_child("high", child2)

    selected = scanner.select_node(root)
    assert selected == child2
