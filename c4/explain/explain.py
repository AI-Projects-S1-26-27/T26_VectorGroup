"""Turn the facts of the chosen move into an Explanation.       OWNER: Naman

explain_move(trace) picks the top 1-3 concepts (by c4/explain/concepts.py priority)
among the facts the rules found for the chosen move, and builds a sentence from
them. Every phrase comes from a fact that was actually detected, so the agent
never claims a reason it did not have. If no rule fired, it falls back to the
score-only sentence from c4/agent.py.

Sentence wording belongs to Aditya (c4/explain/templates.py). If that module has
a function  render(concepts, facts, trace) -> str  it is used; until then the
plain phrases below are used.
"""
from __future__ import annotations

import importlib

from c4.explain.concepts import rank
from c4.trace import Explanation, Fact, SearchTrace, is_decided, own_moves_to_win

PHRASES = {
    "win": "it wins the game",
    "block": "it blocks your four-in-a-row",
    "fork": "it makes {n} threats at once, so you cannot block them all",
    "trap": "it lets you win on top of it, but every other move was worse",
    "sacrifice": "it looks worse at first sight, but the search shows it pays off",
    "threat": "it threatens to win in column {c} next move",
    "setup": "it sets up a threat in column {c}, row {r} for later",
    "centre": "it takes the centre column, which is part of the most lines of four",
}


def facts_for(concepts: list[str], facts: list[Fact]) -> list[Fact]:
    return [f for f in facts if f.kind in concepts]


def _usable(facts: list[Fact]) -> list[str]:
    kinds = {f.kind for f in facts}
    # a plain "threat" fact that is not playable is already said by "setup"
    if not any(f.kind == "threat" and f.detail == "playable" for f in facts):
        kinds.discard("threat")
    return rank(kinds)


def _phrase(kind: str, facts: list[Fact]) -> str:
    f = next(f for f in facts if f.kind == kind
             and (kind != "threat" or f.detail == "playable"))
    target = f.cells[0] if f.cells else (0, f.col or 0)
    return PHRASES[kind].format(c=target[1] + 1, r=target[0] + 1, n=len(f.cells))


def _score_clause(trace: SearchTrace) -> str:
    score = trace.score
    if is_decided(score) and score > 0:
        n = own_moves_to_win(score)
        return f"I can force a win in {n} move{'s' if n != 1 else ''}."
    if is_decided(score):
        return "I am losing by force, and this move delays it the longest."
    return (f"Looking {trace.depth} plies ahead, my score went from "
            f"{trace.static_score} to {score}.")


def _render(concepts: list[str], facts: list[Fact], trace: SearchTrace) -> str:
    try:
        render = getattr(importlib.import_module("c4.explain.templates"), "render", None)
    except ModuleNotFoundError as err:
        if err.name != "c4.explain.templates":
            raise
        render = None
    if render is not None:
        return render(concepts, facts, trace)
    reasons = " and ".join(_phrase(k, facts) for k in concepts)
    return f"I played column {trace.chosen + 1} because {reasons}. {_score_clause(trace)}"


def explain_move(trace: SearchTrace) -> Explanation:
    facts = trace.moves[trace.chosen].facts
    concepts = _usable(facts)
    if not concepts:
        # shortcut: no saliency fallback yet; add c4/nn/saliency once Sriyanth's API is fixed
        from c4.agent import score_only_explanation
        return score_only_explanation(trace)
    used = facts_for(concepts, facts)
    return Explanation(sentence=_render(concepts, used, trace), concepts=concepts,
                       facts=used, score_before=trace.static_score,
                       score_after=trace.score)
