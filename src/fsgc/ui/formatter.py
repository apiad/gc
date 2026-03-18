from typing import Any

from rich.text import Text
from rich.tree import Tree


def format_size(size: float) -> str:
    """
    Format size in bytes to human-readable format.
    """
    is_negative = size < 0
    size = abs(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            formatted = f"{size:.2f} {unit}"
            return f"-{formatted}" if is_negative else formatted

        size = size / 1024.0

    formatted = f"{size:.2f} PB"
    return f"-{formatted}" if is_negative else formatted


def format_speed(bytes_per_sec: float) -> str:
    """
    Format speed in bytes/sec to human-readable format.
    """
    return f"{format_size(bytes_per_sec)}/s"


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
    # Use estimated size for total tree percentage
    if total_size == 0:
        total_size = summary.get("estimated_size", summary["size"])

    node_size = summary.get("estimated_size", summary["size"])
    percentage = (node_size / total_size * 100) if total_size > 0 else 0

    label = Text()

    state = summary.get("state", "VERIFIED")
    completion_ratio = summary.get("completion_ratio", 1.0)

    name_style = "bold blue"
    if state == "ENQUEUED":
        name_style = "dim blue"
    elif state == "EXPLORING":
        name_style = "bold yellow"

    if summary.get("is_others"):
        label.append("...", style="bold yellow")
    else:
        label.append(summary["name"], style=name_style)

    if state == "ENQUEUED":
        label.append(" ⌛", style="yellow")
    elif state == "EXPLORING":
        label.append(" 🔍", style="bold yellow")
        label.append(" ")
        label.append(render_sparkline(completion_ratio))
    elif state == "FINISHED":
        label.append(" ✅", style="green")
    else:
        label.append(" ❓", style="dim")

    label.append(" - ", style="dim")

    # Show Confirmed vs Estimated if different
    confirmed = summary.get("confirmed_size", summary["size"])
    estimated = summary.get("estimated_size", summary["size"])

    if state != "FINISHED" and confirmed < estimated:
        label.append(format_size(confirmed), style="green")
        label.append(f" (~{format_size(estimated)})", style="dim green")
    else:
        label.append(format_size(confirmed), style="green")

    label.append(f" ({percentage:.1f}%)", style="magenta")

    if summary.get("speed"):
        label.append(f" [{format_speed(summary['speed'])}]", style="bold yellow")

    tree = Tree(label)

    for child in summary.get("children", []):
        tree.add(render_summary_tree(child, total_size))

    return tree
