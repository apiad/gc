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


def render_sparkline(ratio: float, length: int = 5) -> Text:
    """
    Render a small sparkline-like progress bar using dots.
    """
    done_count = int(ratio * length)
    spark = Text()
    spark.append("●" * done_count, style="red")
    spark.append("○" * (length - done_count), style="dim gray")
    return spark


def render_summary_tree(summary: dict[str, Any], total_size: int = 0) -> Tree:
    """
    Convert the summary dictionary into a Rich Tree.
    """
    if total_size == 0:
        total_size = summary["size"]

    percentage = (summary["size"] / total_size * 100) if total_size > 0 else 0

    label = Text()

    state = summary.get("state", "VERIFIED")
    completion_ratio = summary.get("completion_ratio", 1.0)

    name_style = "bold blue"
    if state == "GHOST":
        name_style = "dim blue"
    elif state == "STALE":
        name_style = "dim blue"

    if summary.get("is_others"):
        label.append("...", style="bold yellow")
    else:
        label.append(summary["name"], style=name_style)
        if state == "STALE":
            label.append(" ⌛", style="yellow")
            label.append(" ")
            label.append(render_sparkline(completion_ratio))
        elif state == "GHOST":
            label.append(" 💾", style="dim")
            label.append(" ")
            label.append(render_sparkline(completion_ratio))
        else:
            label.append(" ✅", style="dim")

    label.append(" - ", style="dim")

    # Dim the size if it's not fully verified
    size_style = "green" if state == "VERIFIED" else "dim green"
    label.append(format_size(summary["size"]), style=size_style)
    label.append(f" ({percentage:.1f}%)", style="magenta")

    tree = Tree(label)

    for child in summary.get("children", []):
        tree.add(render_summary_tree(child, total_size))

    return tree
