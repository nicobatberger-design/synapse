# Synapse

> **A typed knowledge graph that links your AI agent's brains (rules, procedures, memories) so every task starts armed with the right context.**

Synapse is a tiny, dependency-free framework (Python stdlib only) for giving an AI agent a *structured*, *queryable* memory instead of a pile of loose notes. It merges two worlds into one graph:

- **Living notes** — plain markdown files with `[[wikilinks]]` (Obsidian-style).
- **Brains** — small JSON stores of hard knowledge: **rules** (things the agent must respect) and **procedures** (things the agent knows how to do).

Everything becomes **typed nodes** connected by **typed edges**, so an agent (or you) can ask: *"what surrounds this rule?"* and get its proof notes, the procedures that apply it, and the projects it concerns — in milliseconds, offline, with zero API calls.

## Philosophy

**Learn once, capitalize immediately, execute in minutes.**

1. Something happens during a session (a mistake, a discovery, a repeated task).
2. The learning is **routed** to the right brain as a *candidate* (never auto-promoted — a human validates).
3. Once validated, it lives in the graph, linked to its evidence.
4. Every future task starts by querying the graph: the agent begins *armed*, not amnesiac.

## The graph

```
                 notes/*.md                    brains/*.json
              (wikilinked notes)            (rules, procedures)
                     │                              │
                     ▼                              ▼
              ┌─────────────────────────────────────────┐
              │            synapse/graph.py             │
              │   typed nodes  +  typed edges  (JSON)   │
              └─────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼

  note:deploy-checklist ──references──▶ note:server-setup
        ▲                                     ▲
   proves│                                    │documents
        │                                     │
  rule:review-before-send ◀──applies── procedure:deploy-website
        │                                     │
     concerns                             belongs_to
        ▼                                     ▼
  project:demo-website                 project:demo-website

  brains/private/  ──────  NEVER enters the graph. Ever.
```

### Node types

| Type | Comes from |
|---|---|
| `note` | markdown files in `notes/` |
| `rule` | `brains/rules/rules.json` |
| `procedure` | `brains/procedures/procedures.json` |
| `project` | inferred from `projects/<name>/...` note paths |
| `log`, `decision`, `moc`, ... | the `type:` field of a note's YAML frontmatter |

### Edge types

| Edge | Meaning |
|---|---|
| `references` | note A wikilinks note B |
| `proves` | a rule points to the note that is its evidence |
| `documents` | a procedure points to its documentation note |
| `applies` | a rule/procedure invokes another rule/procedure |
| `concerns` | a rule/procedure is about a note or project |
| `belongs_to` | a note lives inside a project folder |
| `replaces` | a newer note supersedes an older one (`superseded_by:` frontmatter) |

### The private brain

`brains/private/` holds a **policy file only** — categories of information (credentials, personal data, health, finances...) that must **never** be indexed, embedded, exported, or written into the graph. The graph builder excludes the folder unconditionally; the router flags learnings that smell private instead of storing them.

## Quickstart

```bash
git clone <your-fork> synapse && cd synapse

# 1. Build the graph from the bundled fake examples
python -m synapse.graph build

# 2. Query the neighborhood of a rule (depth 2)
python -m synapse.graph neighbors rule:review-before-send 2

# 3. Route a new learning to the right brain (as a candidate)
python -m synapse.route "Always run the test suite before tagging a release"

# 4. Run the full demo
python examples/demo.py
```

Requirements: Python 3.9+. No pip installs. No network.

## Layout

```
synapse/
├── synapse/
│   ├── graph.py        # graph builder + neighbors() query (stdlib only)
│   └── route.py        # routes learnings to brain candidate queues
├── brains/
│   ├── rules/rules.json           # validated rules (schema documented inside)
│   ├── procedures/procedures.json # validated procedures
│   └── private/policy.json        # never-indexed categories (policy only)
├── notes/              # your markdown notes with [[wikilinks]]
├── examples/demo.py    # end-to-end runnable demo
└── graph.json          # generated output (gitignored)
```

## Make it yours

- Drop your own markdown notes in `notes/` (YAML frontmatter + `[[wikilinks]]`).
- Add rules and procedures to the brains as you validate candidates from `_candidates.json` files.
- Point your agent's session bootstrap at `neighbors()` so it loads only the relevant subgraph, not your whole vault.

All content shipped in this repo is **fictional example data**. Replace it.

## License

MIT — see [LICENSE](LICENSE).

---

## 🇫🇷 Synapse en français

**Synapse est un graphe de connaissances typé qui relie les « cerveaux » de votre agent IA (règles, procédures, mémoires) pour que chaque tâche démarre armée du bon contexte.**

- Les **notes** markdown (wikilinks façon Obsidian) et les **brains** JSON (règles, procédures) fusionnent en un seul graphe : nœuds typés, arêtes typées (`proves`, `applies`, `references`, `replaces`...).
- La requête `neighbors(id, profondeur)` renvoie le sous-graphe pertinent : l'agent charge uniquement ce qui sert la tâche, pas tout le coffre.
- Les **apprentissages** d'une session sont **routés** vers des files de candidats (`_candidates.json`) — règle, procédure, ou signalement privé — puis validés par un humain avant d'entrer dans le graphe.
- Le **brain privé** n'est jamais indexé : c'est une politique d'exclusion inconditionnelle, pas une option.

Philosophie : **apprendre une fois, capitaliser immédiatement, exécuter en minutes.**

Démarrage : `python -m synapse.graph build` puis `python examples/demo.py`. Python 3.9+, bibliothèque standard uniquement, aucun réseau.
