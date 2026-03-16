import time

from fsgc.config import Signature
from fsgc.scanner import DirectoryNode


class HeuristicEngine:
    """
    Scores DirectoryNodes based on pattern matching, recency, and regenerability.
    """

    def __init__(self, age_threshold_days: int = 90) -> None:
        self.age_threshold = age_threshold_days * 24 * 60 * 60  # Convert to seconds
        self.now = time.time()

        # Weights for the scoring formula
        self.w_pattern = 0.5
        self.w_recency = 0.3
        self.w_priority = 0.2

    def get_matching_signature(
        self, node: DirectoryNode, signatures: list[Signature]
    ) -> Signature | None:
        """
        Check if a node's path matches any signature pattern.
        """
        for sig in signatures:
            if node.path.match(sig.pattern):
                return sig
        return None

    def calculate_score(self, node: DirectoryNode, signature: Signature | None) -> float:
        """
        Calculate score S(n) = w1*P(n) + w2*A(n) + w3*R(n)
        """
        p_score = 1.0 if signature else 0.0

        age_seconds = self.now - node.atime
        a_score = min(1.0, max(0.0, age_seconds / self.age_threshold))

        r_score = signature.priority if signature else 0.0

        score = (
            (self.w_pattern * p_score) + (self.w_recency * a_score) + (self.w_priority * r_score)
        )
        return min(1.0, max(0.0, score))

    def apply_scoring(
        self, node: DirectoryNode, signatures: list[Signature]
    ) -> dict[DirectoryNode, tuple[float, Signature]]:
        """
        Recursively score nodes and return a mapping of node to its score and signature.
        """
        scores: dict[DirectoryNode, tuple[float, Signature]] = {}

        signature = self.get_matching_signature(node, signatures)

        if signature:
            score = self.calculate_score(node, signature)
            scores[node] = (score, signature)

        for child in node.children.values():
            scores.update(self.apply_scoring(child, signatures))

        return scores
