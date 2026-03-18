import fnmatch
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
        # Adjusted for more aggressive weighting for pattern and priority
        self.w_pattern = 0.6
        self.w_priority = 0.3
        self.w_recency = 0.1

        # Caching matchers to avoid redundant pattern analysis
        self._matchers: list[tuple[bool, str, Signature]] | None = None
        self._exact_sentinels: set[str] = set()
        self._glob_sentinels: list[str] = []

    def _get_matchers(self, signatures: list[Signature]) -> list[tuple[bool, str, Signature]]:
        """
        Analyze signatures and return a list of (is_simple, pattern, signature).
        'is_simple' means it can be matched by exact directory name.
        """
        matchers = []
        for sig in signatures:
            pattern = sig.pattern
            # Optimization: if pattern is "**/name" and contains no other globs, it's simple
            is_simple = False
            match_pattern = pattern
            if pattern.startswith("**/"):
                base_pattern = pattern[3:]
                # Optimization: if it's a single-level name without globs, it's simple
                if "/" not in base_pattern and not any(c in base_pattern for c in "*?[]"):
                    is_simple = True
                    match_pattern = base_pattern

            matchers.append((is_simple, match_pattern, sig))

            # Track all sentinels
            for sentinel in sig.sentinels:
                if any(c in sentinel for c in "*?[]"):
                    if sentinel not in self._glob_sentinels:
                        self._glob_sentinels.append(sentinel)
                else:
                    self._exact_sentinels.add(sentinel)

        return matchers

    def is_relevant_evidence(self, name: str) -> bool:
        """
        Check if a filename or suffix matches any sentinel defined in any signature.
        """
        if name in self._exact_sentinels:
            return True
        for glob in self._glob_sentinels:
            if fnmatch.fnmatch(name, glob):
                return True
        return False

    def _verify_sentinels(self, node: DirectoryNode, sig: Signature) -> bool:
        if not sig.sentinels:
            return True
        for sentinel in sig.sentinels:
            for ev in node.file_evidence:
                if fnmatch.fnmatch(ev, sentinel) or ev == sentinel:
                    return True
        return False

    def get_matching_signature(
        self, node: DirectoryNode, signatures: list[Signature]
    ) -> Signature | None:
        """
        Check if a node's path matches any signature pattern.
        Uses a fast-path for simple name-based patterns.
        """
        if self._matchers is None:
            self._matchers = self._get_matchers(signatures)

        for is_simple, pattern, sig in self._matchers:
            matched = False
            if is_simple:
                if node.path.name == pattern:
                    matched = True
            else:
                if node.path.match(sig.pattern):
                    matched = True

            if matched and self._verify_sentinels(node, sig):
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

        score = (
            (self.w_pattern * p_score) + (self.w_priority * r_score) + (self.w_recency * a_score)
        )
        return min(1.0, max(0.0, score))

    def apply_scoring(
        self, node: DirectoryNode, signatures: list[Signature]
    ) -> dict[DirectoryNode, tuple[float, Signature]]:
        """
        Recursively score nodes and return a mapping of node to its score and signature.
        """
        scores: dict[DirectoryNode, tuple[float, Signature]] = {}

        # Use cached signature if available
        signature = node.signature or self.get_matching_signature(node, signatures)

        if signature:
            score = self.calculate_score(node, signature)
            if score > 0:
                scores[node] = (score, signature)
                # If we matched this folder, we don't usually need to suggest its subfolders
                return scores

        for child in node.children.values():
            scores.update(self.apply_scoring(child, signatures))

        return scores
