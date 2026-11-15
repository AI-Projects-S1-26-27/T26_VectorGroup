"""Concept hierarchy for explanations (T1 Ch. 10, categories).   OWNER: Naman

Every Fact.kind the rules produce is a concept. Concepts sit in a small is-a tree
and carry a priority, so the explanation can report the most important 1-3.

    concept
    ├── tactic
    │   ├── attack   : win, fork, threat, setup
    │   ├── defence  : block
    │   └── danger   : trap
    ├── strategy     : sacrifice
    └── positional   : centre
"""
from __future__ import annotations

PARENT = {
    "tactic": "concept", "strategy": "concept", "positional": "concept",
    "attack": "tactic", "defence": "tactic", "danger": "tactic",
    "win": "attack", "fork": "attack", "threat": "attack", "setup": "attack",
    "block": "defence",
    "trap": "danger",
    "sacrifice": "strategy",
    "centre": "positional",
}

# higher = said first; only the leaf concepts (Fact kinds) need one
PRIORITY = {
    "win": 100,
    "block": 90,
    "fork": 80,
    "trap": 70,
    "sacrifice": 60,
    "threat": 50,
    "setup": 40,
    "centre": 10,
}


def ancestors(kind: str) -> list[str]:
    """['fork', 'attack', 'tactic', 'concept'] for 'fork'."""
    out = [kind]
    while out[-1] in PARENT:
        out.append(PARENT[out[-1]])
    return out


def is_a(kind: str, category: str) -> bool:
    return category in ancestors(kind)


def rank(kinds, top: int = 3) -> list[str]:
    """Distinct known concepts, highest priority first, at most `top`."""
    return sorted({k for k in kinds if k in PRIORITY}, key=PRIORITY.get, reverse=True)[:top]
