"""Synapse learning router.

Takes a raw learning (one sentence or paragraph captured during an agent
session) and routes it to the right brain as a *candidate*:

- rule candidate      -> brains/rules/_candidates.json
- procedure candidate -> brains/procedures/_candidates.json
- private flag        -> brains/private/_candidates.json (flag only — the
                         learning text is NOT stored when it smells private)

Nothing is ever auto-promoted into ``rules.json`` / ``procedures.json``:
a human reviews the candidate queues and moves validated entries by hand.
That review step is the whole safety model.

Deterministic keyword heuristics, standard library only, no network.

Usage:
    python -m synapse.route "Always re-read a message before sending it"
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUES = {
    "rule": ROOT / "brains" / "rules" / "_candidates.json",
    "procedure": ROOT / "brains" / "procedures" / "_candidates.json",
    "private": ROOT / "brains" / "private" / "_candidates.json",
}
POLICY_PATH = ROOT / "brains" / "private" / "policy.json"

# Normative language -> probably a rule.
_RULE_MARKERS = {
    "always", "never", "must", "must not", "forbidden", "mandatory",
    "toujours", "jamais", "interdit", "obligatoire", "ne pas",
}
# Step-by-step / how-to language -> probably a procedure.
_PROCEDURE_MARKERS = {
    "how to", "steps", "step 1", "first", "then", "finally", "checklist",
    "procedure", "workflow", "deploy", "install", "configure", "run",
    "etapes", "d'abord", "ensuite", "enfin", "procedure", "lancer",
}


def _norm(text: str) -> str:
    """Lowercase + strip accents: 'Toujours' -> 'toujours'."""
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


def _private_keywords() -> list[str]:
    """Detection keywords come from the private brain's policy file."""
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        words = []
        for category in policy.get("categories", []):
            words.extend(category.get("keywords", []))
        return [_norm(w) for w in words]
    except Exception:
        # No policy -> be conservative with a minimal builtin list.
        return ["password", "api key", "token", "secret", "credential"]


def classify(learning: str) -> str:
    """'private' beats everything; then 'rule'; then 'procedure'; default 'rule'."""
    text = _norm(learning)
    if any(kw in text for kw in _private_keywords()):
        return "private"
    rule_score = sum(1 for m in _RULE_MARKERS if m in text)
    proc_score = sum(1 for m in _PROCEDURE_MARKERS if m in text)
    if proc_score > rule_score:
        return "procedure"
    return "rule"


def _slug(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _norm(text)).strip("-")
    return slug[:max_len].rstrip("-") or "candidate"


def route(learning: str, source: str = "session") -> dict:
    """Append the learning to the matching candidate queue; return the entry."""
    kind = classify(learning)
    entry = {
        # private learnings get an opaque id: even the slug must not leak text
        "id": time.strftime("private-%Y%m%d-%H%M%S") if kind == "private" else _slug(learning),
        "kind": kind,
        "captured": time.strftime("%Y-%m-%d %H:%M"),
        "source": source,
        "status": "pending_review",
    }
    if kind == "private":
        # Flag only: the sensitive text itself is never persisted.
        entry["note"] = "learning matched a private-policy category; text withheld"
    else:
        entry["text"] = learning.strip()

    queue_path = QUEUES[kind]
    try:
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        if not isinstance(queue, list):
            queue = []
    except Exception:
        queue = []
    queue.append(entry)
    queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
    return entry


def main() -> None:
    if len(sys.argv) < 2:
        print('usage: python -m synapse.route "<learning text>"')
        sys.exit(2)
    entry = route(" ".join(sys.argv[1:]))
    print(f"routed as {entry['kind']} candidate -> {QUEUES[entry['kind']]}")
    print(json.dumps(entry, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
