from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Signature:
    """
    Represents a garbage pattern signature.
    """

    name: str
    pattern: str
    priority: float
    min_age_days: int = 0


class SignatureManager:
    """
    Manages loading and matching of garbage signatures.
    """

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.signatures: list[Signature] = []
        self.load()

    def load(self) -> None:
        """
        Load signatures from the YAML configuration file.
        """
        if not self.config_path.exists():
            return

        with open(self.config_path) as f:
            data = yaml.safe_load(f)

        if not data or "signatures" not in data:
            return

        for s in data["signatures"]:
            self.signatures.append(
                Signature(
                    name=s["name"],
                    pattern=s["pattern"],
                    priority=float(s["priority"]),
                    min_age_days=int(s.get("min_age_days", 0)),
                )
            )
