"""Answer the four question types during a game.                OWNER: Aditya

    answer(question, game, agent=None) -> str

question   typed text, or a button payload {"intent": "why_not", "column": 5}
game       c4.game.GameState (board, history, human_first, last_trace, last_explanation)
agent      anything with analyse(board) -> SearchTrace. Needed only to search a NEW
           position ("what if", or "who is winning" before the agent has moved).
           If omitted we use game.agent, else a small heuristic agent.

Why / why not / who is winning mostly READ the saved trace (last_trace is the
agent's trace from BEFORE its last move). What if runs one new search on a copy of
the board, so the real game is never touched. Columns: the player says 1-7, the
code uses 0-6; converted once, here.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from c4.board import Board
from c4.explain import templates as T
from c4.qa.parser import HELP, Intent, Question, QuestionError, parse_question
from c4.trace import SearchTrace, is_decided, plies_to_end

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ helpers
def _agent_player(game) -> int:
    return 1 if game.human_first else 0          # 0 = first player (X)


@lru_cache(maxsize=1)
def _default_agent():
    from c4.agent import Agent
    from c4.eval_heuristic import HeuristicEvaluator
    return Agent(HeuristicEvaluator(), time_limit=0.5)


def _history_ok(game, trace: SearchTrace) -> bool:
    """last_trace must describe the position the game is in now: the agent just
    moved, or the human has answered it since."""
    if trace.board.player_to_move != _agent_player(game):
        return False
    after_ai = trace.board.play_unchecked(trace.chosen)
    if after_ai == game.board:
        return True
    return (not after_ai.is_over() and
            any(after_ai.play_unchecked(c) == game.board for c in after_ai.legal_moves()))


def _explain(trace: SearchTrace):
    """Naman's explain_move if it is on main, else the plain score sentence."""
    try:
        from c4.explain.explain import explain_move
        return explain_move(trace)
    except (ImportError, NotImplementedError):
        from c4.agent import score_only_explanation
        return score_only_explanation(trace)


def _to_agent_view(score: int, board: Board, game) -> int:
    """A search score is from the view of the player to move at `board`."""
    return score if board.player_to_move == _agent_player(game) else -score


# ---------------------------------------------------------------- the entry
def answer(question, game, agent=None) -> str:
    board = game.board
    if board.is_over():
        return _game_over(game)
    try:
        if isinstance(question, dict):
            q = Question(question.get("intent"), question.get("column"))
        else:
            q = parse_question(question)
    except QuestionError as err:
        return str(err)

    try:
        if q.intent == Intent.WHAT_IF:
            return _what_if(q.column - 1, game, agent)
        if q.intent == Intent.WHO_WINNING:
            return _who_winning(game, agent)
        trace = game.last_trace
        if trace is None:
            return "I haven't made a move yet, so there is nothing to explain. " + HELP
        if not _history_ok(game, trace):
            return "My saved move does not match this position any more, so I can't explain it."
        if q.intent == Intent.WHY:
            return _why(game, trace)
        return _why_not(q.column - 1, trace)
    except _NoSearch:
        return "I can't search that position right now. Please try again. " + HELP


class _NoSearch(RuntimeError):
    pass


def _analyse(board: Board, game, agent) -> SearchTrace:
    agent = agent or getattr(game, "agent", None)
    try:
        agent = agent or _default_agent()
        return agent.analyse(board)
    except Exception as err:                      # details to the log, not the player
        log.exception("search failed")
        raise _NoSearch from err


# ------------------------------------------------------------------ handlers
def _game_over(game) -> str:
    b = game.board
    if b.last_mover_won():
        winner = 1 - b.player_to_move
        who = "I won" if winner == _agent_player(game) else "you won"
    else:
        who = "it is a draw"
    return f"The game is over: {who}. Start a new game to ask more questions."


def _why(game, trace: SearchTrace) -> str:
    exp = getattr(game, "last_explanation", None)
    if exp is not None and exp.sentence:
        return exp.sentence
    return _explain(trace).sentence


def _why_not(col: int, trace: SearchTrace) -> str:
    shown = col + 1
    if col not in trace.moves:
        return f"Column {shown} was full when I chose my move, so it was not an option."
    if col == trace.chosen:
        return f"Column {shown} is the move I played. " + T.render(
            T.concepts_of(trace.moves[col].facts), trace.moves[col].facts, trace)
    mine, other = trace.moves[trace.chosen], trace.moves[col]
    parts = [f"I chose column {trace.chosen + 1} instead of column {shown}."]
    if mine.exact and other.exact:
        parts.append(f"After looking {T.plies_text(trace.depth)} ahead, "
                     f"{T.column_result(trace.chosen + 1, mine.score)}, while "
                     f"{T.column_result(shown, other.score)}.")
        if mine.score == other.score:
            parts.append("They tied, so the score gives no reason to prefer either.")
    else:
        parts.append("The search only has a bound for one of them, so I can't give an "
                     "exact comparison.")
    reasons = T.phrases_for(T.concepts_of(other.facts), other.facts, chosen=False)
    if reasons:
        parts.append(f"About column {shown}: " + T._join(reasons) + ".")
    parts.append(T.continuation_text(other.pv, first_is_agent=True))
    return " ".join(parts)


def _what_if(col: int, game, agent) -> str:
    board, shown = game.board, col + 1
    if board.player_to_move == _agent_player(game):
        return "Wait for my move first, then ask what you could play. " + HELP
    if col not in board.legal_moves():
        return f"Column {shown} is full. Choose another column."
    after = board.play_unchecked(col)             # a new Board; the game is untouched
    prefix = f"If you play column {shown}, "
    if after.last_mover_won():
        return prefix + "you complete four in a row and win."
    if after.is_over():
        return prefix + "the board is full and the game is a draw."
    trace = _analyse(after, game, agent)
    sentence = _explain(trace).sentence
    if sentence.startswith("I played"):
        sentence = "I would play" + sentence[len("I played"):]
    return (prefix + sentence + " " + T.continuation_text(trace.moves[trace.chosen].pv, True)
            + " This is a what-if search; your game has not changed.")


def _who_winning(game, agent) -> str:
    board = game.board
    trace = game.last_trace
    if trace is not None and _history_ok(game, trace) \
            and trace.board.play_unchecked(trace.chosen) == board:
        score, mover, depth = trace.score, trace.board.player_to_move, trace.depth
    else:                                          # no usable trace: search this board
        t = _analyse(board, game, agent)
        score, mover, depth = t.score, board.player_to_move, t.depth
    agent_score = score if mover == _agent_player(game) else -score
    if is_decided(score):
        plies = plies_to_end(score)
        winner_is_mover = score > 0
        n = (plies + 1) // 2 if winner_is_mover else plies // 2
        winner_is_agent = (mover == _agent_player(game)) == winner_is_mover
        who = "I can" if winner_is_agent else "you can"
        return (f"{who[0].upper() + who[1:]} force a win in {n} move{'s' if n != 1 else ''} "
                f"against best play (found by search, {T.plies_text(plies)}).")
    return (f"After looking {T.plies_text(depth)} ahead, {T.advantage_text(agent_score)}. "
            f"My score is {agent_score}. That is an estimate, not a proven result.")
