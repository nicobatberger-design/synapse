"""End-to-end Synapse demo.

Builds the graph from the bundled fictional notes and brains, then prints
the typed neighborhood of a rule and of a procedure.

Run from the repository root:
    python examples/demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from synapse.graph import build, neighbors  # noqa: E402


def show(result: dict) -> None:
    print(f"\n=== neighbors of {result['center']} ===")
    for node in result["nodes"]:
        marker = "*" if node["id"] == result["center"] else " "
        print(f" {marker} [{node['type']:9s}] {node['id']}  — {node['title']}")
    print(" edges:")
    for edge in result["edges"]:
        print(f"   {edge['from']}  --{edge['type']}-->  {edge['to']}")


def main() -> None:
    graph = build()
    show(neighbors("rule:review-before-send", depth=2, graph=graph))
    show(neighbors("procedure:weekly-backup", depth=1, graph=graph))


if __name__ == "__main__":
    main()
