"""Explanation rules, applied by forward chaining (T1 Ch. 7, 9).   OWNER: Naman

detect_facts(trace) looks at every root move in the SearchTrace and fills
MoveInfo.facts with the tactical facts that are TRUE for that move. The agent
(c4/agent.py) calls it right after the search.

Each rule is a production: it reads the board facts (c4/explain/facts.py), the
search trace and the facts derived so far (working memory), and adds new facts.
Rules are fired over and over until nothing new is added. Base rules work on
the board; derived rules (fork, setup) fire on facts made by other rules.

Facts are always about the side that is making the root move (the agent):
  win        playing here wins at once
  block      the opponent could win here next move; this stops it
  threat     the move makes a NEW cell where the agent would complete four
             (detail: "playable" if it can be played next move, else "odd"/"even" row)
  fork       derived: two or more playable threats at once, they cannot all be blocked
  setup      derived: a new threat that is not playable yet (a threat for later)
  trap       the move lets the opponent win by playing on top of it
  centre     the move is in the centre column
  sacrifice  the static score drops after the move but the search score is higher

Fact.cells lists the target cell first, then the stones of the line it uses,
so eval/claim_check.py can check every claim by brute force.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass

from c4.board import Board, HEIGHT
from c4.explain.facts import is_odd_row, playable_cells, threat_cells
from c4.trace import Fact, MoveInfo, SearchTrace


@dataclass
class Context:
    """Everything a rule may look at for one root move. Arrays use +1 = agent."""
    board: Board          # root position, agent to move
    col: int
    row: int              # row the agent's stone lands on
    child: Board          # position after the move (opponent to move)
    before: object        # 6x7 array of `board`
    after: object         # 6x7 array of `child`
    move: MoveInfo
    static_before: int
    evaluator: object     # for "sacrifice"; None = rule is skipped


def _won(facts) -> bool:
    return any(f.kind == "win" for f in facts)


def _line_fact(kind, target, line, arr, who, detail=""):
    stones = [cell for cell in line if cell != target and arr[cell[0]][cell[1]] == who]
    return Fact(kind=kind, col=target[1], cells=[target, *stones], detail=detail)


# ---------------------------------------------------------------- base rules
def rule_win(ctx, facts):
    if ctx.board.wins_by_playing(ctx.col):
        target = (ctx.row, ctx.col)
        line = threat_cells(ctx.before, 1)[target]
        return [_line_fact("win", target, line, ctx.before, 1)]
    return []


def rule_block(ctx, facts):
    if _won(facts):
        return []
    target = (ctx.row, ctx.col)
    line = threat_cells(ctx.before, -1).get(target)
    return [_line_fact("block", target, line, ctx.before, -1)] if line else []


def rule_threat(ctx, facts):
    if _won(facts):
        return []
    old = threat_cells(ctx.before, 1)
    playable = playable_cells(ctx.child)
    out = []
    for target, line in sorted(threat_cells(ctx.after, 1).items()):
        if target in old:
            continue
        if target in playable:
            detail = "playable"
        else:
            detail = "odd" if is_odd_row(target[0]) else "even"
        out.append(_line_fact("threat", target, line, ctx.after, 1, detail))
    return out


def rule_trap(ctx, facts):
    if _won(facts) or ctx.row + 1 >= HEIGHT:
        return []
    target = (ctx.row + 1, ctx.col)
    line = threat_cells(ctx.after, -1).get(target)
    return [_line_fact("trap", target, line, ctx.after, -1)] if line else []


def rule_centre(ctx, facts):
    if ctx.col == 3:
        return [Fact(kind="centre", col=3, cells=[(ctx.row, 3)])]
    return []


def rule_sacrifice(ctx, facts):
    if ctx.evaluator is None or _won(facts) or ctx.child.is_over():
        return []
    static_after = -ctx.evaluator.evaluate(ctx.child)    # back to the agent's view
    if static_after < ctx.static_before < ctx.move.score:
        return [Fact(kind="sacrifice", col=ctx.col, cells=[(ctx.row, ctx.col)],
                     detail=f"static {ctx.static_before}->{static_after}, "
                            f"search {ctx.move.score}")]
    return []


# ------------------------------------------------------------- derived rules
def rule_fork(ctx, facts):
    # shortcut: only counts threats NEW to this move, so an old threat that this move
    # makes playable is missed. This can only miss forks, never claim a false one.
    playable = [f for f in facts if f.kind == "threat" and f.detail == "playable"]
    if len(playable) >= 2:
        return [Fact(kind="fork", col=ctx.col, cells=[f.cells[0] for f in playable],
                     detail=f"{len(playable)} threats")]
    return []


def rule_setup(ctx, facts):
    return [Fact(kind="setup", col=f.col, cells=list(f.cells), detail=f.detail)
            for f in facts if f.kind == "threat" and f.detail != "playable"]


RULES = (rule_win, rule_block, rule_threat, rule_trap, rule_centre,
         rule_sacrifice, rule_fork, rule_setup)


def forward_chain(ctx: Context) -> list[Fact]:
    """Fire every rule until no rule adds a new fact."""
    facts: list[Fact] = []
    changed = True
    while changed:
        changed = False
        for rule in RULES:
            for fact in rule(ctx, facts):
                if fact not in facts:
                    facts.append(fact)
                    changed = True
    return facts


_network = None


def network_evaluator():
    """The default NNEvaluator, loaded once; None if torch or the weights are missing.
    shortcut: always the default weights (models/nn_latest.pt or $C4_MODEL), not
    whatever file the agent was given; pass `evaluator=` to detect_facts if they differ."""
    global _network
    if _network is None:
        try:
            _network = importlib.import_module("c4.nn.evaluator").NNEvaluator()
        except (ImportError, FileNotFoundError):
            return None
    return _network


def _default_evaluator(trace: SearchTrace):
    """The evaluator that scored the trace, so the sacrifice rule compares scores
    from the SAME evaluator. None if it is not available."""
    if trace.evaluator == "heuristic":
        return importlib.import_module("c4.eval_heuristic").HeuristicEvaluator()
    if trace.evaluator == "network":
        return network_evaluator()
    return None


def move_context(board: Board, move: MoveInfo, static_before: int = 0,
                 evaluator=None) -> Context:
    child = board.play(move.col)
    return Context(board=board, col=move.col, row=board.height(move.col), child=child,
                   before=board.to_array(), after=-child.to_array(), move=move,
                   static_before=static_before, evaluator=evaluator)


def detect_facts(trace: SearchTrace, evaluator=None) -> SearchTrace:
    """Fill MoveInfo.facts for every root move (replacing what was there)."""
    if evaluator is None:
        evaluator = _default_evaluator(trace)
    for move in trace.moves.values():
        ctx = move_context(trace.board, move, trace.static_score, evaluator)
        move.facts = forward_chain(ctx)
    return trace
