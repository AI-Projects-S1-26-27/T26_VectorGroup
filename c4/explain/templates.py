"""Sentence templates: concepts + facts + trace -> English.     OWNER: Aditya

Every phrase is tied to a Fact that a rule really found (c4/explain/rules.py), so
the agent never states a reason it did not have. Nothing here searches or decides;
it only words what it is given.

Entry point (called by c4/explain/explain.py):
    render(concepts, facts, trace) -> str
Helpers used by c4/qa/answers.py: fact_phrase, score_clause, column_result,
advantage_text, continuation_text.
"""
from __future__ import annotations

from c4.trace import (SearchTrace, Fact, is_decided, own_moves_to_win,
                      plies_to_end)

from c4.explain.concepts import rank          # Naman's concept priorities

# Display bands for NON-decided scores (heuristic/network units, about +-900 in
# practice). These are labels for the player, not win probabilities.
SLIGHT, CLEAR = 50, 250


def plies_text(n: int) -> str:
    return f"{n} ply" if n == 1 else f"{n} plies"


def _col(fact: Fact) -> int:
    """Column of the fact's target cell, 1-7 for the player."""
    return (fact.cells[0][1] if fact.cells else (fact.col or 0)) + 1


def _join(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def fact_phrase(fact: Fact, *, chosen: bool = True) -> str:
    """One clause for one fact. chosen=False words it for a move NOT played."""
    kind = fact.kind
    if kind == "win":
        return "it completes four in a row and wins the game"
    if kind == "block":
        return "it blocks your four-in-a-row"
    if kind == "fork":
        cols = _join([str(c[1] + 1) for c in fact.cells])
        return f"it makes {len(fact.cells)} threats at once (columns {cols}), so you cannot block them all"
    if kind == "trap":
        tail = ", but the search still rated it best" if chosen else ""
        return f"it lets you win by playing on top of it in column {_col(fact)}{tail}"
    if kind == "sacrifice":
        return "it looks worse at first sight, but the search score is higher"
    if kind == "threat":
        return f"it threatens to win in column {_col(fact)} next move"
    if kind == "setup":
        return f"it sets up a threat in column {_col(fact)}, row {fact.cells[0][0] + 1} for later"
    if kind == "centre":
        return "it takes the centre column, which is part of the most lines of four"
    raise ValueError(f"no template for fact kind {kind!r}")


def concepts_of(facts: list[Fact]) -> list[str]:
    """Top concepts among a move's facts. A 'threat' that is not playable is already
    said by 'setup', so it is dropped (same rule as explain.py)."""
    kinds = {f.kind for f in facts}
    if not any(f.kind == "threat" and f.detail == "playable" for f in facts):
        kinds.discard("threat")
    return rank(kinds)


def phrases_for(concepts: list[str], facts: list[Fact], *, chosen: bool = True) -> list[str]:
    """One phrase per concept, in the order given (highest priority first).
    A fact kind with no template yet (a new rule) is skipped, never a crash."""
    out = []
    for kind in concepts:
        fact = next((f for f in facts if f.kind == kind
                     and (kind != "threat" or f.detail == "playable")), None)
        if fact is None:
            continue
        try:
            out.append(fact_phrase(fact, chosen=chosen))
        except ValueError:
            continue
    return out


def column_result(col_shown: int, score: int) -> str:
    """What the search found for one root column, in plain words.
    `score` is from the AGENT's point of view (the player to move at the trace's root).
    Proven results are given as moves to win, the way the proposal words them."""
    if is_decided(score):
        plies = plies_to_end(score)
        if score > 0:                              # the agent's own moves, incl. the root move
            n = (plies + 1) // 2
            return f"column {col_shown} lets me force a win in {n} move{'s' if n != 1 else ''}"
        n = plies // 2                             # the opponent's moves
        return (f"after column {col_shown} you can force a win in "
                f"{n} move{'s' if n != 1 else ''}")
    return f"column {col_shown} scores {score}"


def score_clause(trace: SearchTrace) -> str:
    score = trace.score
    if is_decided(score) and score > 0:
        n = own_moves_to_win(score)
        return f"I can force a win in {n} move{'s' if n != 1 else ''}."
    if is_decided(score):
        return "I am losing by force, and this move delays it the longest."
    return (f"Looking {plies_text(trace.depth)} ahead, my score went from "
            f"{trace.static_score} to {score}.")


def render(concepts: list[str], facts: list[Fact], trace: SearchTrace) -> str:
    """The agent's explanation of its chosen move."""
    reasons = _join(phrases_for(concepts, facts))
    head = f"I played column {trace.chosen + 1}"
    head += f" because {reasons}." if reasons else "."
    return f"{head} {score_clause(trace)}"


def advantage_text(agent_score: int) -> str:
    """Heuristic score from the AGENT's point of view -> who looks better."""
    if agent_score >= CLEAR:
        return "I appear to have the advantage"
    if agent_score >= SLIGHT:
        return "I appear to have a slight edge"
    if agent_score <= -CLEAR:
        return "you appear to have the advantage"
    if agent_score <= -SLIGHT:
        return "you appear to have a slight edge"
    return "the position looks roughly balanced"


def continuation_text(pv: list[int], first_is_agent: bool, limit: int = 6) -> str:
    """Expected line of play. pv is 0-6 columns; shown as 1-7."""
    if not pv:
        return "No continuation was recorded."
    steps = []
    for i, col in enumerate(pv[:limit]):
        mine = (i % 2 == 0) == first_is_agent
        steps.append(f"{'me' if mine else 'you'}: {col + 1}")
    end = " -> ..." if len(pv) > limit else "."
    return "Expected line: " + " -> ".join(steps) + end
