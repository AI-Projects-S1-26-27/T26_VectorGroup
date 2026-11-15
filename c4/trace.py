"""The search trace and the other shared data types.       OWNER: Shridali

The search WRITES a SearchTrace; the explanation layer and the question
answering layer only READ it. Everyone codes against these classes, so change
them only after telling the group.

Score convention
----------------
A score is always from the point of view of the player TO MOVE at the board it
is attached to (negamax convention).
  * heuristic / network scores:  integers in [-MAX_HEURISTIC, MAX_HEURISTIC]
  * a forced win in `p` plies from the root:   WIN_SCORE - p
  * a forced loss in `p` plies from the root: -(WIN_SCORE - p)
  * a draw: 0
Plies are counted from the root, so "I win with my 4th stone from now" = 7 plies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from c4.board import Board, SIZE

WIN_SCORE = 100_000
MAX_HEURISTIC = 9_999
NN_SCALE = 1_000          # network output in (-1, 1)  ->  int(round(v * NN_SCALE))


def is_decided(score: int) -> bool:
    """True if the score is a proven win or loss (not just a heuristic guess)."""
    return abs(score) > WIN_SCORE - SIZE - 1


def plies_to_end(score: int) -> int:
    """For a decided score: plies from the root until the game ends."""
    return WIN_SCORE - abs(score)


def own_moves_to_win(score: int) -> int:
    """For a decided WINNING score: how many of the mover's own moves it takes
    (this includes the winning move).  7 plies -> 4 moves."""
    return (plies_to_end(score) + 1) // 2


@dataclass
class Fact:
    """One tactical fact found by the rule layer (explain/rules.py)."""
    kind: str                      # e.g. "win", "block", "fork", "trap", "setup",
                                   #      "sacrifice", "centre"
    col: Optional[int] = None      # column it is about (0-6), if any
    cells: list = field(default_factory=list)   # [(row, col), ...]  row 0 = bottom
    detail: str = ""               # short machine-readable note


@dataclass
class MoveInfo:
    """Everything the search found out about ONE root move."""
    col: int                       # 0-6
    score: int                     # exact score of playing this move (see above)
    depth: int                     # depth this score was searched to
    pv: list[int]                  # expected line of play, starts with `col`
    exact: bool = True             # searched with a full window => score is exact
    facts: list[Fact] = field(default_factory=list)   # filled by explain/rules.py


@dataclass
class SearchTrace:
    board: Board                   # the root position (player to move = the agent)
    chosen: int                    # column the agent plays
    depth: int                     # deepest completed iteration
    nodes: int                     # nodes searched in total
    time_s: float
    evaluator: str                 # "heuristic" or "network"
    static_score: int              # evaluator(board) BEFORE searching (for "sacrifice")
    moves: dict[int, MoveInfo]     # col -> MoveInfo, one entry per legal root move

    @property
    def score(self) -> int:
        return self.moves[self.chosen].score

    def ranked(self) -> list[MoveInfo]:
        """Root moves, best first."""
        return sorted(self.moves.values(), key=lambda m: m.score, reverse=True)


@dataclass
class Explanation:
    """What the agent says about one move (built by explain/explain.py)."""
    sentence: str                  # the English explanation shown to the user
    concepts: list[str]            # top 1-3 concepts used, highest priority first
    facts: list[Fact]              # the facts those concepts came from
    score_before: int              # static score of the root position
    score_after: int               # search score of the move