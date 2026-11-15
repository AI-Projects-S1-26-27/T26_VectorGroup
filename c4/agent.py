"""The agent: search + explanation glued together.        

This is what the web server and the question-answering layer call.

    agent.analyse(board)      -> SearchTrace   search, then the rule layer adds tactical facts
    agent.play_turn(game)     -> TurnResult    column to play, the trace, and the explanation

play_turn does NOT change the game. The caller applies the result with
game.record_agent_turn(result).

The explanation parts belong to other people (Naman: c4/explain/rules.py and
c4/explain/explain.py). They are looked up when needed, so this file works before
they exist: without them the agent gives a plain score-only sentence. Once their
files are merged, they are used automatically.
"""
from __future__ import annotations

import importlib

from c4.board import Board
from c4.evaluator import Evaluator
from c4.game import GameState, TurnResult
from c4.search import search
from c4.trace import Explanation, SearchTrace, is_decided, own_moves_to_win


def _optional(module_name: str, attr: str):
    """Return module.attr, or None if that module/function has not been written yet.
    Any other error (a real bug inside the module) is NOT hidden."""
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as err:
        if err.name == module_name:
            return None
        raise
    return getattr(module, attr, None)


def score_only_explanation(trace: SearchTrace) -> Explanation:
    """Plain sentence built from the score alone. Used when the rule layer is not
    available, and as the 'score only' baseline in the explanation rating study."""
    col = trace.chosen + 1
    score = trace.score
    if is_decided(score) and score > 0:
        n = own_moves_to_win(score)
        text = f"I played column {col}. I can force a win in {n} move{'s' if n != 1 else ''}."
    elif is_decided(score):
        text = f"I played column {col}. I am losing by force, and this move delays it the longest."
    else:
        text = f"I played column {col}. After looking {trace.depth} plies ahead its score is {score}."
    return Explanation(sentence=text, concepts=[], facts=[],
                       score_before=trace.static_score, score_after=score)


class Agent:
    name = "agent"

    def __init__(self, evaluator: Evaluator, time_limit: float = 1.0, tt=None, order_fn=None):
        self.evaluator = evaluator
        self.time_limit = time_limit
        self.tt = tt
        self.order_fn = order_fn

    def analyse(self, board: Board) -> SearchTrace:
        """Search `board` and add tactical facts to every root move. No move is made."""
        trace = search(board, self.evaluator, time_limit=self.time_limit,
                       tt=self.tt, order_fn=self.order_fn)
        detect_facts = _optional("c4.explain.rules", "detect_facts")
        if detect_facts is not None:
            try:
                detect_facts(trace)
            except NotImplementedError:
                pass                      # file exists but is still a stub
        return trace

    def play_turn(self, game: GameState) -> TurnResult:
        trace = self.analyse(game.board)
        return TurnResult(col=trace.chosen, trace=trace, explanation=self._explain(trace))

    def _explain(self, trace: SearchTrace) -> Explanation:
        explain_move = _optional("c4.explain.explain", "explain_move")
        if explain_move is not None:
            try:
                return explain_move(trace)
            except NotImplementedError:
                pass
        return score_only_explanation(trace)