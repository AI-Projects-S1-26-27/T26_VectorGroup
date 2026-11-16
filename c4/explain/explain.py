"""Turn the facts of the chosen move into an Explanation.       OWNER: Naman

explain_move(trace) picks the top 1-3 concepts (by c4/explain/concepts.py priority)
among the facts the rules found for the chosen move, and builds a sentence from
them. Every phrase comes from a fact that was actually detected, so the agent
never claims a reason it did not have. If no rule fired, a network-scored move is
explained with occlusion saliency (c4/nn/saliency.py); otherwise it falls back to
the score-only sentence from c4/agent.py.

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


def _saliency_explanation(trace: SearchTrace):
    """Quiet move (no rule fired) scored by the network: say which stone made the
    network like the position most (Sriyanth's c4/nn/saliency.py)."""
    from c4.explain.rules import network_evaluator
    from c4.nn.saliency import move_saliency
    ev = network_evaluator()
    if ev is None:
        return None
    sal = move_saliency(trace.board, trace.chosen, ev, k=1)
    if not sal["cells"]:
        return None
    top = sal["cells"][0]
    whose = "my" if top["owner"] == "mover" else "your"
    effect = "helps me" if top["delta"] > 0 else "is a problem for me"
    sentence = (f"I played column {trace.chosen + 1}. There is no direct tactic here, "
                f"but my network rates the position after it at {sal['value']:+.2f} for me, "
                f"and {whose} stone in column {top['col'] + 1}, row {top['row'] + 1} "
                f"{effect} the most. {_score_clause(trace)}")
    fact = Fact(kind="saliency", col=top["col"], cells=[(top["row"], top["col"])],
                detail=f"value {sal['value']:+.2f}, delta {top['delta']:+.2f}")
    return Explanation(sentence=sentence, concepts=["saliency"], facts=[fact],
                       score_before=trace.static_score, score_after=trace.score)


def explain_move(trace: SearchTrace) -> Explanation:
    facts = trace.moves[trace.chosen].facts
    concepts = _usable(facts)
    if not concepts:
        if trace.evaluator == "network":
            expl = _saliency_explanation(trace)
            if expl is not None:
                return expl
        from c4.agent import score_only_explanation
        return score_only_explanation(trace)
    used = facts_for(concepts, facts)
    return Explanation(sentence=_render(concepts, used, trace), concepts=concepts,
                       facts=used, score_before=trace.static_score,
                       score_after=trace.score)
