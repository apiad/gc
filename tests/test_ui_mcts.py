from rich.tree import Tree

from fsgc.ui.formatter import render_summary_tree


def test_render_exploring_state():
    summary = {
        "name": "root",
        "size": 100,
        "estimated_size": 1000,
        "confirmed_size": 100,
        "state": "EXPLORING",
        "completion_ratio": 0.1,
        "is_others": False,
        "children": [],
    }

    tree = render_summary_tree(summary)
    assert isinstance(tree, Tree)
    label = tree.label
    # Rich Text can be checked for style or content
    label_text = str(label)
    assert "root" in label_text
    assert "100.00 B" in label_text
    assert "1000.00 B" in label_text
    assert "🔍" in label_text
