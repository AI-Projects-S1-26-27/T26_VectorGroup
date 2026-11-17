"""Turn the facts of the chosen move into an Explanation.       OWNER: Naman

explain_move(trace) picks the top 1-3 concepts (by c4/explain/concepts.py priority)
among the facts the rules found for the chosen move, and has Aditya's templates
(c4/explain/templates.py) word them. Every phrase comes from a fact that was
actually detected, so the agent never claims a reason it did not have. If no rule
fired, a network-scored move is explained with occlusion saliency
(c4/nn/saliency.py); otherwise it falls back to the score-only sentence from
c4/agent.py.
"""
from __future__ import annotations

from c4.explain import templates as T
from c4.trace import Explanation, Fact, SearchTrace


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
                f"{effect} the most. {T.score_clause(trace)}")
    fact = Fact(kind="saliency", col=top["col"], cells=[(top["row"], top["col"])],
                detail=f"value {sal['value']:+.2f}, delta {top['delta']:+.2f}")
    return Explanation(sentence=sentence, concepts=["saliency"], facts=[fact],
                       score_before=trace.static_score, score_after=trace.score)


def explain_move(trace: SearchTrace) -> Explanation:
    facts = trace.moves[trace.chosen].facts
    concepts = T.concepts_of(facts)
    if not concepts:
        if trace.evaluator == "network":
            expl = _saliency_explanation(trace)
            if expl is not None:
                return expl
        from c4.agent import score_only_explanation
        return score_only_explanation(trace)
    used = [f for f in facts if f.kind in concepts]
    return Explanation(sentence=T.render(concepts, used, trace), concepts=concepts,
                       facts=used, score_before=trace.static_score,
                       score_after=trace.score)
