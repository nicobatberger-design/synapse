"""Synapse graph engine.

Builds a single typed knowledge graph from two sources:

1. Markdown notes (``notes/``) — YAML frontmatter + ``[[wikilinks]]``.
2. Brains (``brains/``) — JSON stores of rules and procedures.

Nodes are typed (note, rule, procedure, project, log, decision, moc...).
Edges are typed (references, proves, documents, applies, concerns,
belongs_to, replaces).

The private brain (``brains/private/``) is NEVER walked, parsed, or linked:
exclusion is unconditional, by construction.

Standard library only. Output: ``graph.json`` at the repository root.

Usage:
    python -m synapse.graph build
    python -m synapse.graph neighbors <node_id> [depth]
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = ROOT / "notes"
RULES_PATH = ROOT / "brains" / "rules" / "rules.json"
PROCEDURES_PATH = ROOT / "brains" / "procedures" / "procedures.json"
OUT_PATH = ROOT / "graph.json"

# Never index anything under these folders (the private brain above all).
EXCLUDED_DIRS = {"private", "_candidates", ".git"}

_WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")

# Note frontmatter `type:` values kept as-is; anything else collapses to "note".
_NOTE_TYPES = {"log", "decision", "moc", "template", "project"}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Minimal YAML frontmatter parser (key: value pairs only)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip().strip("'\"")
    return meta, text[end + 4:]


def _note_id(relpath: str) -> str:
    return "note:" + (relpath[:-3] if relpath.endswith(".md") else relpath)


def _collect_notes(notes_dir: Path) -> tuple[dict, list, dict]:
    """Walk the notes tree -> typed note nodes + wikilink/project/replaces edges."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    stems: dict[str, str] = {}  # lowercase filename stem -> node id
    raw: list[tuple[str, str, str, dict]] = []

    for path in sorted(notes_dir.rglob("*.md")):
        rel = path.relative_to(notes_dir).as_posix()
        if any(part in EXCLUDED_DIRS for part in Path(rel).parts):
            continue
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("status", "").lower() in ("superseded", "expired"):
            continue  # stale knowledge stays out of the living graph
        nid = _note_id(rel)
        ntype = meta.get("type", "").lower()
        if ntype not in _NOTE_TYPES:
            ntype = "note"
        nodes[nid] = {"id": nid, "type": ntype, "title": meta.get("title") or path.stem}
        stems[path.stem.lower()] = nid
        raw.append((nid, body, rel, meta))

    for nid, body, rel, meta in raw:
        # notes under projects/<name>/ belong to a project node
        match = re.match(r"projects/([^/]+)/", rel)
        if match:
            pid = "project:" + match.group(1)
            nodes.setdefault(pid, {"id": pid, "type": "project", "title": match.group(1)})
            edges.append({"from": nid, "to": pid, "type": "belongs_to"})
        # superseded_by: newer note replaces this one
        successor = meta.get("superseded_by", "").strip().strip("[]").lower()
        if successor in stems:
            edges.append({"from": stems[successor], "to": nid, "type": "replaces"})
        # wikilinks -> untyped "references" edges (the Obsidian inheritance)
        for m in _WIKILINK_RE.finditer(body):
            target = m.group(1).strip().split("/")[-1].lower()
            tid = stems.get(target)
            if tid and tid != nid:
                edges.append({"from": nid, "to": tid, "type": "references"})

    return nodes, edges, stems


def _resolve_link(token: str, stems: dict) -> str | None:
    """'rule:x' / 'procedure:x' / 'project:x' -> as-is; otherwise resolve a note stem."""
    token = token.strip()
    if token.startswith(("rule:", "procedure:", "project:")):
        return token
    if token.startswith("note:"):
        token = token[5:]
    return stems.get(Path(token).stem.lower())


def _collect_brains(nodes: dict, edges: list, stems: dict) -> None:
    """Merge the rule and procedure brains into the graph with typed edges."""
    specs = (
        (RULES_PATH, "rule", "rules", "title", "proves"),
        (PROCEDURES_PATH, "procedure", "procedures", "name", "documents"),
    )
    for path, kind, list_key, name_key, source_edge in specs:
        if not path.is_file():
            continue
        entries = json.loads(path.read_text(encoding="utf-8")).get(list_key, [])
        for entry in entries:
            nid = f"{kind}:{entry['id']}"
            nodes[nid] = {"id": nid, "type": kind, "title": entry.get(name_key, entry["id"])}
        for entry in entries:
            nid = f"{kind}:{entry['id']}"
            # `source` = documentary evidence (several files may be joined with '+')
            for part in re.split(r"[+,]", str(entry.get("source", ""))):
                tid = _resolve_link(part, stems)
                if tid and tid != nid:
                    edges.append({"from": nid, "to": tid, "type": source_edge})
            # `links` = cross-brain and cross-note relations
            for link in entry.get("links", []) or []:
                tid = _resolve_link(link, stems)
                if tid and tid != nid:
                    etype = "applies" if tid.startswith(("rule:", "procedure:")) else "concerns"
                    edges.append({"from": nid, "to": tid, "type": etype})


def build(notes_dir: Path = NOTES_DIR, out_path: Path = OUT_PATH, log=print) -> dict:
    """Build the full graph and write it to ``out_path``."""
    started = time.time()
    nodes, edges, stems = _collect_notes(notes_dir)
    _collect_brains(nodes, edges, stems)

    # keep deduplicated edges whose both endpoints exist
    seen, kept = set(), []
    for edge in edges:
        key = (edge["from"], edge["to"], edge["type"])
        if key in seen or edge["from"] not in nodes or edge["to"] not in nodes:
            continue
        seen.add(key)
        kept.append(edge)

    graph = {
        "meta": {
            "generated": time.strftime("%Y-%m-%d %H:%M"),
            "version": 1,
            "node_count": len(nodes),
            "edge_count": len(kept),
        },
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "edges": kept,
    }
    out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"graph: {len(nodes)} nodes, {len(kept)} edges in {time.time() - started:.2f}s -> {out_path}")
    return graph


def load(path: Path = OUT_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def neighbors(node_id: str, depth: int = 1, graph: dict | None = None) -> dict:
    """Typed neighborhood of a node — the subgraph an agent should load for a task."""
    g = graph or load()
    adjacency: dict[str, list] = {}
    for edge in g["edges"]:
        adjacency.setdefault(edge["from"], []).append(edge)
        adjacency.setdefault(edge["to"], []).append(edge)

    frontier, keep_nodes, keep_edges = {node_id}, {node_id}, []
    for _ in range(max(1, depth)):
        nxt: set[str] = set()
        for nid in frontier:
            for edge in adjacency.get(nid, []):
                keep_edges.append(edge)
                for endpoint in (edge["from"], edge["to"]):
                    if endpoint not in keep_nodes:
                        nxt.add(endpoint)
        keep_nodes |= nxt
        frontier = nxt

    index = {n["id"]: n for n in g["nodes"]}
    unique = {(e["from"], e["to"], e["type"]): e for e in keep_edges}
    return {
        "center": node_id,
        "nodes": [index[i] for i in sorted(keep_nodes) if i in index],
        "edges": list(unique.values()),
    }


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "neighbors":
        if len(args) < 2:
            print("usage: python -m synapse.graph neighbors <node_id> [depth]")
            sys.exit(2)
        result = neighbors(args[1], int(args[2]) if len(args) > 2 else 1)
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return
    graph = build()
    degree: dict[str, int] = {}
    for edge in graph["edges"]:
        degree[edge["from"]] = degree.get(edge["from"], 0) + 1
        degree[edge["to"]] = degree.get(edge["to"], 0) + 1
    index = {n["id"]: n for n in graph["nodes"]}
    print("Top 5 most connected nodes:")
    for nid, deg in sorted(degree.items(), key=lambda x: -x[1])[:5]:
        print(f"  {deg:4d}  {nid}  ({index[nid]['type']} — {index[nid]['title']})")


if __name__ == "__main__":
    main()
