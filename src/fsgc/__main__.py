import asyncio
import datetime
import shutil
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.live import Live

from fsgc.aggregator import group_by_signature, summarize_tree
from fsgc.config import SignatureManager
from fsgc.engine import HeuristicEngine
from fsgc.scanner import DirectoryNode, Scanner
from fsgc.trail import GCTrail
from fsgc.ui.formatter import format_size, render_summary_tree
from fsgc.ui.prompt import prompt_confirm_action, prompt_for_deletion

app = typer.Typer(name="gc", help="Garbage Collector for your filesystem.")
console = Console()


def sweep(selected_groups: list[dict[str, Any]], dry_run: bool = True) -> None:
    """
    Perform the actual or simulated deletion of selected garbage nodes.
    """
    total_reclaimed = 0

    for group in selected_groups:
        console.print(f"\n[bold]Collecting: {group['name']}[/]")
        for node in group["nodes"]:
            if dry_run:
                console.print(
                    f"[yellow]DRY RUN:[/] Would delete {node.path} ({format_size(node.size)})"
                )
                total_reclaimed += node.size
            else:
                try:
                    if node.path.is_dir():
                        shutil.rmtree(node.path)
                    else:
                        node.path.unlink()
                    console.print(f"[green]Deleted:[/] {node.path}")
                    total_reclaimed += node.size
                except Exception as e:
                    console.print(f"[red]Error deleting {node.path}: {e}[/]")

    status = "Simulated" if dry_run else "Successfully"
    console.print(f"\n[bold green]{status} reclaimed {format_size(total_reclaimed)}![/]")


@app.command()
def scan(
    path: Annotated[Path, typer.Argument(help="Root path to start scanning from.")] = Path("."),
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be collected without deleting.")
    ] = False,
    min_size: Annotated[
        int, typer.Option("--min-size", help="Minimum size in bytes to report.")
    ] = 0,
    depth: Annotated[int, typer.Option("--depth", "-d", help="Maximum display depth.")] = 2,
    min_percent: Annotated[
        float, typer.Option("--min-percent", "-p", help="Minimum size percentage of parent.")
    ] = 0.05,
    limit: Annotated[
        int, typer.Option("--limit", "-l", help="Maximum number of children to list individually.")
    ] = 10,
    age_threshold: Annotated[
        int, typer.Option("--age", "-a", help="Age threshold in days for recency heuristic.")
    ] = 90,
) -> None:
    """
    gc: A heuristic-based garbage collector for your filesystem.

    Scans a directory for garbage and proposes collection.
    """
    path = path.resolve()
    console.print(f"[bold blue]Scanning[/] {path}...")

    # Phase 1: Scan and build tree (Live Updates)
    scanner = Scanner(path)

    async def run_scan() -> DirectoryNode:
        root_node = None
        with Live(console=console, refresh_per_second=10) as live:
            async for snapshot in scanner.scan():
                root_node = snapshot
                # Phase 2: Hierarchy Summary (Traditional Scan view)
                summary = summarize_tree(
                    root_node,
                    max_depth=depth,
                    min_percent=min_percent,
                    max_children=limit,
                    min_size=min_size,
                )
                tree = render_summary_tree(summary)
                live.update(tree)
        return root_node

    root_node = asyncio.run(run_scan())
    console.print(f"\nTotal size: [bold]{format_size(root_node.size)}[/].")

    # Phase 1.5: Persist trails
    with console.status("[bold green]Persisting directory trails...[/]"):
        asyncio.run(scanner.persist_trails(root_node))

    # Phase 3: Mark (Scoring)
    config_path = Path("config/signatures.yaml")
    sig_manager = SignatureManager(config_path)
    engine = HeuristicEngine(age_threshold_days=age_threshold)

    with console.status("[bold yellow]Applying heuristics and scoring...[/]"):
        node_scores = engine.apply_scoring(root_node, sig_manager.signatures)

    # Phase 4: Aggregate (Grouping)
    groups = group_by_signature(node_scores)

    # Phase 5: Prompt (Interactive Selection)
    if not groups:
        console.print("\n[green]No garbage matching your signatures was found.[/]")
        return

    console.print("\n[bold yellow]Garbage Collection Proposal:[/]")
    selected_groups = prompt_for_deletion(groups)

    if not selected_groups:
        console.print("[yellow]No items selected. Aborting.[/]")
        return

    # Phase 6: Sweep (Final Action)
    action = "dry" if dry_run else prompt_confirm_action()

    if action == "abort":
        console.print("[red]Aborted.[/]")
    elif action == "dry":
        sweep(selected_groups, dry_run=True)
    elif action == "run":
        sweep(selected_groups, dry_run=False)


@app.command()
def trail_dump(path: Annotated[Path, typer.Argument(help="Path to the .gctrail file.")]) -> None:
    """
    Debug command to dump the contents of a .gctrail binary file.
    """
    if not path.exists():
        console.print(f"[red]Error:[/] File {path} does not exist.")
        raise typer.Exit(1)

    try:
        data = path.read_bytes()
        trail = GCTrail.from_bytes(data)

        console.print(f"[bold blue]Trail Summary for {path}[/]")
        ts_str = datetime.datetime.fromtimestamp(trail.timestamp, datetime.UTC)
        console.print(f"  Timestamp: [green]{ts_str}[/]")
        console.print(f"  Structural Hash: [yellow]{trail.structural_hash}[/]")
        console.print(f"  Total Size: [bold]{format_size(trail.total_size)}[/]")
        console.print(f"  Reconstructible: [bold]{format_size(trail.reconstructible_size)}[/]")
        console.print(f"  Noise: [bold]{format_size(trail.noise_size)}[/]")

        if trail.big_fish:
            console.print("\n[bold]Big Fish (>10MB):[/]")
            for fish in trail.big_fish:
                console.print(f"  - {fish.filename} ({format_size(fish.size)})")
        else:
            console.print("\n[italic]No Big Fish found.[/]")

    except Exception as e:
        console.print(f"[red]Error parsing trail file:[/] {e}")
        raise typer.Exit(1) from e


def run() -> None:
    """
    Entry point for the CLI.
    """
    app()


if __name__ == "__main__":
    run()
