import asyncio
from pathlib import Path

from fsgc.scanner import DirectoryNode, Scanner


async def reproduce() -> None:
    # Setup mock deep tree
    # root -> a -> b -> c -> d -> files
    root_path = Path("./mock_root")
    root_path.mkdir(exist_ok=True)
    current = root_path
    for char in "abcd":
        current = current / char
        current.mkdir(exist_ok=True)

    (current / "file.txt").write_text("hello" * 1000)  # 500 bytes

    scanner = Scanner(root=root_path, max_concurrency=1)

    # 1. Expand root manually to get children
    root_node = DirectoryNode(path=root_path)
    scanner.tree = root_node
    await scanner._process_directory(root_node)

    child_a = list(root_node.children.values())[0]
    print(f"Child A path: {child_a.path}")

    # 2. Simulate worker processing subtree starting at child_a
    # This should go deep and find the file
    await scanner.mcts_iteration(child_a)  # Iteration 1: expand a
    await scanner.mcts_iteration(child_a)  # Iteration 2: expand b
    await scanner.mcts_iteration(child_a)  # Iteration 3: expand c
    await scanner.mcts_iteration(child_a)  # Iteration 4: expand d

    print(f"Child A confirmed size: {child_a.confirmed_size}")
    print(f"Child A dirty: {child_a.dirty}")

    # 3. Now check absolute root metadata
    # The scan() loop does this:
    root_node.dirty = True
    root_node.calculate_metadata()

    print(f"Root confirmed size: {root_node.confirmed_size}")

    if root_node.confirmed_size == 0:
        print("FAIL: Root size not updated!")
    else:
        print(
            "PASS: Root size updated (unexpected based on my theory, "
            "let me re-read calculate_metadata)"
        )

    # Let's check intermediate nodes
    child_a_again = list(root_node.children.values())[0]
    print(f"Child A dirty after root calc: {child_a_again.dirty}")


reproduce_path = Path("./mock_root")
try:
    asyncio.run(reproduce())
finally:
    import shutil

    if reproduce_path.exists():
        shutil.rmtree(reproduce_path)
