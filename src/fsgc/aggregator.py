from typing import Any

from fsgc.scanner import DirectoryNode


def summarize_tree(
    node: DirectoryNode,
    max_depth: int,
    min_percent: float = 0.05,
    max_children: int = 4,
    current_depth: int = 0,
    min_size: int = 0,
) -> dict[str, Any]:
    """
    Recursively summarize a DirectoryNode tree into a format suitable for TUI rendering.

    Filtering Rules:
    1. Descend up to max_depth.
    2. Only show nodes larger than min_size.
    3. Sort children by size (descending).
    4. Keep children where (child.size / node.size) >= min_percent.
    5. Keep at most max_children individual children.
    6. Group remaining size into an "Others" virtual node.
    """
    summary: dict[str, Any] = {
        "name": node.path.name or str(node.path),
        "size": node.size,
        "is_others": False,
        "children": [],
    }

    if current_depth >= max_depth or not node.children:
        return summary

    # Sort children by size
    sorted_children = sorted(node.children.values(), key=lambda x: x.size, reverse=True)

    keep_count = 0
    total_child_size_shown = 0

    children_list: list[dict[str, Any]] = []

    for child in sorted_children:
        # Check if we should keep this child individually
        percentage = child.size / node.size if node.size > 0 else 0

        should_keep = (
            keep_count < max_children and percentage >= min_percent and child.size >= min_size
        )

        if should_keep:
            child_summary = summarize_tree(
                child, max_depth, min_percent, max_children, current_depth + 1, min_size
            )
            children_list.append(child_summary)
            total_child_size_shown += child.size
            keep_count += 1
        else:
            # This child and all subsequent ones will be grouped in "Others"
            break

    # Calculate "Others" size: (Total node size) - (Sizes of shown children)
    others_size = node.size - total_child_size_shown

    if others_size > 0 and (others_size / node.size if node.size > 0 else 0) > 0.001:
        children_list.append(
            {"name": "Others", "size": others_size, "is_others": True, "children": []}
        )

    summary["children"] = children_list
    return summary
