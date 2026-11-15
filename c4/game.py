"""Game session types.                                    OWNER: Shridali"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from c4.board import Board
from c4.trace import SearchTrace, Explanation


@dataclass
class GameState:
    board: Board = field(default_factory=Board.empty)   # current position
    history: list[int] = field(default_factory=list)    # all moves so far, cols 0-6
    human_first: bool = True                            # human = X (moves first)?
    # Trace of the agent's MOST RECENT decision; trace.board is the position
    # BEFORE the agent moved. None until the agent has moved once.
    last_trace: Optional[SearchTrace] = None
    last_explanation: Optional[Explanation] = None

    def apply_move(self, col: int) -> None:
        self.board = self.board.play(col)
        self.history.append(col)

    def record_agent_turn(self, result: "TurnResult") -> None:
        """Play the agent's move and remember its trace and explanation, so the
        question-answering layer can read them."""
        self.apply_move(result.col)
        self.last_trace = result.trace
        self.last_explanation = result.explanation


@dataclass
class TurnResult:
    col: int                       # column the agent plays (0-6)
    trace: SearchTrace
    explanation: Explanation