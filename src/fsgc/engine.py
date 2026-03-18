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
        if not signature:
            return 0.0

        age_seconds = self.now - node.atime
        min_age_seconds = signature.min_age_days * 24 * 60 * 60

        # Filter out if too young
        if age_seconds < min_age_seconds:
            return 0.0

        p_score = 1.0  # We have a signature match

        # a_score is 1.0 if age >= threshold, scaled otherwise
        a_score = min(1.0, max(0.0, age_seconds / self.age_threshold))

        r_score = signature.priority

        # More aggressive weighting for pattern and priority
        w_pattern = 0.6
        w_priority = 0.3
        w_recency = 0.1

        score = (w_pattern * p_score) + (w_priority * r_score) + (w_recency * a_score)
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
            if score > 0:
                scores[node] = (score, signature)
                # If we matched this folder, we don't usually need to suggest its subfolders
                return scores

        for child in node.children.values():
            scores.update(self.apply_scoring(child, signatures))

        return scores
