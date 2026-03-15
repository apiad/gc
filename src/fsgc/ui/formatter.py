from typing import Any

from rich.text import Text
from rich.tree import Tree


def format_size(size: int) -> str:
    """
    Format size in bytes to human-readable format.
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size //= 1024
    return f"{size:.1f} PB"


def render_summary_tree(summary: dict[str, Any], total_size: int = 0) -> Tree:
    """
    Convert the summary dictionary into a Rich Tree.
    """
    if total_size == 0:
        total_size = summary["size"]

    percentage = (summary["size"] / total_size * 100) if total_size > 0 else 0

    label = Text()
    if summary.get("is_others"):
        label.append(summary["name"], style="italic yellow")
    else:
        label.append(summary["name"], style="bold blue")

    label.append(" - ", style="dim")
    label.append(format_size(summary["size"]), style="green")
    label.append(f" ({percentage:.1f}%)", style="magenta")

    tree = Tree(label)

    for child in summary.get("children", []):
        tree.add(render_summary_tree(child, total_size))

    return tree
