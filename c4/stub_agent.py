"""A fake agent so the web UI and the Q&A layer can be built BEFORE the real
engine exists.                                           OWNER: Shridali

It plays random legal moves and returns made-up (but correctly shaped) traces
and explanations. Swap it for c4.agent.Agent once that works - same two methods.
"""
from __future__ import annotations

import random

from c4.board import Board
from c4.game import GameState, TurnResult
from c4.trace import Explanation, MoveInfo, SearchTrace


class StubAgent:
    name = "stub"

    def analyse(self, board: Board) -> SearchTrace:
        moves = board.legal_moves()
        infos = {c: MoveInfo(col=c, score=random.randint(-50, 50), depth=1, pv=[c])
                 for c in moves}
        chosen = max(infos, key=lambda c: infos[c].score)
        return SearchTrace(board=board, chosen=chosen, depth=1, nodes=len(moves),
                           time_s=0.0, evaluator="stub", static_score=0, moves=infos)

    def play_turn(self, game: GameState) -> TurnResult:
        trace = self.analyse(game.board)
        info = trace.moves[trace.chosen]
        expl = Explanation(
            sentence=f"[stub] I played column {trace.chosen + 1} because it scored best.",
            concepts=["centre"], facts=[], score_before=0, score_after=info.score)
        return TurnResult(col=trace.chosen, trace=trace, explanation=expl)