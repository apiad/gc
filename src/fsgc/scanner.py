import logging
import os
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DirectoryNode:
    """
    A node in the directory tree that aggregates sizes.
    """

    path: Path
    size: int = 0  # Total size (self + children)
    files_size: int = 0  # Sum of file sizes in this directory only
    children: dict[str, "DirectoryNode"] = field(default_factory=dict)
    is_dir: bool = True

    def add_child(self, name: str, node: "DirectoryNode") -> None:
        self.children[name] = node


class Scanner:
    """
    A scanner that builds a directory tree and aggregates sizes.
    Optimized for large filesystems using os.scandir.
    """

    def __init__(self, root: Path, stay_on_mount: bool = True) -> None:
        self.root = root.resolve()
        self.stay_on_mount = stay_on_mount
        self.root_dev = self._get_dev(self.root)
        self.tree: DirectoryNode | None = None

    def _get_dev(self, path: Path) -> int:
        try:
            return os.stat(path).st_dev
        except (PermissionError, FileNotFoundError):
            return -1

    def scan(self) -> DirectoryNode:
        """
        Perform a scan of the filesystem and build a DirectoryNode tree.
        Uses BFS to discover directories and build the structure.
        """
        root_node = DirectoryNode(path=self.root)
        self.tree = root_node

        # Mapping from path to node for quick lookup during tree building
        path_to_node: dict[Path, DirectoryNode] = {self.root: root_node}
        queue: deque[Path] = deque([self.root])
        visited: set[str] = {str(self.root)}

        while queue:
            current_path = queue.popleft()
            current_node = path_to_node[current_path]

            try:
                with os.scandir(current_path) as it:
                    for entry in it:
                        entry_path = Path(entry.path)

                        if self.stay_on_mount and self._get_dev(entry_path) != self.root_dev:
                            continue

                        if entry.is_dir(follow_symlinks=False):
                            real_path = os.path.realpath(entry.path)
                            if real_path not in visited:
                                visited.add(real_path)
                                child_node = DirectoryNode(path=entry_path)
                                current_node.add_child(entry.name, child_node)
                                path_to_node[entry_path] = child_node
                                queue.append(entry_path)
                        else:
                            # It's a file, add its size to the current directory
                            try:
                                size = entry.stat(follow_symlinks=False).st_size
                                current_node.files_size += size
                            except (PermissionError, FileNotFoundError):
                                pass

            except (PermissionError, FileNotFoundError) as e:
                logger.debug(f"Skipping {current_path}: {e}")

        self.calculate_sizes(root_node)
        return root_node

    def calculate_sizes(self, node: DirectoryNode) -> int:
        """
        Recursively calculate the total size of each node (bottom-up).
        """
        total_size = node.files_size
        for child in node.children.values():
            total_size += self.calculate_sizes(child)

        node.size = total_size
        return total_size
