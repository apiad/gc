import time
from pathlib import Path

from fsgc.config import Signature
from fsgc.engine import HeuristicEngine
from fsgc.scanner import DirectoryNode


def test_heuristic_engine_scoring() -> None:
    engine = HeuristicEngine()

    # Create a node that matches a signature
    path = Path("node_modules")
    # 100 days old
    atime = time.time() - (100 * 24 * 60 * 60)
    node = DirectoryNode(path=path, size=1000, atime=atime)

    sig = Signature(name="Node Dependencies", pattern="node_modules", priority=0.8)

    score = engine.calculate_score(node, sig)

    # Expected:
    # p_score = 0.5 * 1.0 = 0.5
    # a_score = 0.3 * (100/90 capped at 1.0) = 0.3
    # r_score = 0.2 * 0.8 = 0.16
    # Total = 0.96
    assert score >= 0.9


def test_heuristic_engine_no_match() -> None:
    engine = HeuristicEngine()
    path = Path("src")
    node = DirectoryNode(path=path, size=1000, atime=time.time())  # Brand new

    score = engine.calculate_score(node, None)

    # Expected: 0.0 (no pattern, no age, no priority)
    assert score == 0.0


def test_apply_scoring() -> None:
    engine = HeuristicEngine()
    root = DirectoryNode(path=Path("root"), size=1000)
    node1 = DirectoryNode(path=Path("node_modules"), size=500)
    root.add_child("node_modules", node1)

    sig = Signature(name="Node", pattern="node_modules", priority=1.0)

    scores = engine.apply_scoring(root, [sig])
    assert len(scores) == 1
    assert node1 in scores
    assert scores[node1][1] == sig


def test_engine_optimized_matching():
    from unittest.mock import patch

    engine = HeuristicEngine()

    sigs = [
        Signature(name="Simple", pattern="**/node_modules", priority=0.9),
        Signature(name="Complex", pattern="**/google-chrome-backup-crashrecovery*", priority=0.5),
    ]

    # Test simple name match
    node1 = DirectoryNode(path=Path("/home/user/node_modules"))
    with patch.object(Path, "match", wraps=node1.path.match) as mock_match:
        sig = engine.get_matching_signature(node1, sigs)
        assert sig is not None
        assert sig.name == "Simple"
        # If optimized, match() should NOT be called for node_modules
        assert mock_match.call_count == 0

    # Test complex glob match
    node2 = DirectoryNode(path=Path("/home/user/google-chrome-backup-crashrecovery-123"))
    with patch.object(Path, "match", wraps=node2.path.match) as mock_match:
        sig = engine.get_matching_signature(node2, sigs)
        assert sig is not None
        assert sig.name == "Complex"
        # Complex patterns still need match()
        assert mock_match.call_count > 0
