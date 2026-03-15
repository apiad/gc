from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from fsgc.aggregator import summarize_tree
from fsgc.scanner import Scanner
from fsgc.ui.formatter import format_size, render_summary_tree

app = typer.Typer(name="gc", help="Garbage Collector for your filesystem.")
console = Console()


@app.command()
def main(
    path: Annotated[Path, typer.Argument(help="Root path to start scanning from.")] = Path("."),
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be collected.")
    ] = False,
    min_size: Annotated[
        int, typer.Option("--min-size", help="Minimum size in bytes to report.")
    ] = 0,
    depth: Annotated[int, typer.Option("--depth", "-d", help="Maximum display depth.")] = 3,
    min_percent: Annotated[
        float, typer.Option("--min-percent", "-p", help="Minimum size percentage of parent.")
    ] = 0.05,
    limit: Annotated[
        int, typer.Option("--limit", "-l", help="Maximum number of children to list individually.")
    ] = 4,
) -> None:
    """
    gc: A heuristic-based garbage collector for your filesystem.

    Scans a directory for garbage and proposes collection.
    """
    path = path.resolve()
    console.print(f"[bold blue]Scanning[/] {path}...")

    if dry_run:
        console.print("[yellow]Dry run mode enabled.[/]")

    # Phase 1: Scan and build tree
    scanner = Scanner(path)
    with console.status("[bold green]Building directory tree...[/]"):
        root_node = scanner.scan()

    # Phase 2: Aggregate and summarize
    summary = summarize_tree(
        root_node,
        max_depth=depth,
        min_percent=min_percent,
        max_children=limit,
        min_size=min_size,
    )

    # Phase 3: Render
    console.print("\n[bold]Directory Size Summary:[/]")
    tree = render_summary_tree(summary)
    console.print(tree)

    console.print(
        f"\n[bold green]Scan complete![/] Total size: [bold]{format_size(root_node.size)}[/]."
    )


if __name__ == "__main__":
    app()
