"""The evaluator interface.                               OWNER: Shridali

Search never cares HOW a position is scored, only that the scorer follows this
protocol. Two implementations will exist:
  * c4/eval_heuristic.py  -> HeuristicEvaluator   (Rujuta)
  * c4/nn/evaluator.py    -> NNEvaluator          (Sriyanth)
"""
from __future__ import annotations

from typing import Protocol

from c4.board import Board


class Evaluator(Protocol):
    name: str          # "heuristic" or "network"  (goes into SearchTrace.evaluator)

    def evaluate(self, board: Board) -> int:
        """Score `board` for the player TO MOVE.
        Must return an int in [-MAX_HEURISTIC, MAX_HEURISTIC] (see c4/trace.py).
        Positive = good for the player to move. Must not be called on a finished game."""
        ...