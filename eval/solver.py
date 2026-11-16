"""Perfect Connect-4 solver, used ONLY for testing and evaluation (never by the agent).

OWNER: Mani

Two back ends, same answers:
  * built-in solver (pure Python): negamax + alpha-beta, bitboards, a transposition
    table, "never play a losing move" pruning and move ordering by threat count.
    These are the ideas from Pascal Pons's guide (http://blog.gamesolver.org/).
    Fast enough for positions with roughly 14 or more stones on the board.
  * Pascal Pons's compiled C++ solver, if you have built it. Point the environment
    variable C4_SOLVER_BIN at the `c4solver` executable and every call below uses it
    instead (about 100x faster, needed for positions with very few stones).
    It speaks the same move-string format as Board.from_moves.

Score convention (same as Pons):
    > 0  the player TO MOVE wins; 22 - (stones that player will have played at the end)
    = 0  draw with perfect play
    < 0  the player to move loses
    So +1 is the slowest possible win, +18 the quickest (win with the 4th stone).
Public functions take a Board or a move string such as "4453" (1-indexed columns).
"""
from __future__ import annotations

import os
import subprocess

from c4.board import BOARD_MASK, BOTTOM_MASK, H1, HEIGHT, SIZE, WIDTH, Board, _col_mask

CENTER_FIRST = (3, 2, 4, 1, 5, 0, 6)


def _winning_cells(position: int, mask: int) -> int:
    """Empty cells where `position` would complete four in a row (Pons)."""
    r = (position << 1) & (position << 2) & (position << 3)          # vertical
    for shift in (H1, HEIGHT, HEIGHT + 2):                           # 3 other directions
        p = (position << shift) & (position << 2 * shift)
        r |= p & (position << 3 * shift)
        r |= p & (position >> shift)
        p = (position >> shift) & (position >> 2 * shift)
        r |= p & (position << shift)
        r |= p & (position >> 3 * shift)
    return r & (BOARD_MASK ^ mask)


def _non_losing_moves(position: int, mask: int) -> int:
    """Bitmask of cells the mover can play without losing at once (0 = every move loses)."""
    possible = (mask + BOTTOM_MASK) & BOARD_MASK
    opponent_win = _winning_cells(position ^ mask, mask)
    forced = possible & opponent_win
    if forced:
        if forced & (forced - 1):
            return 0                       # two threats at once: lost
        possible = forced
    return possible & ~(opponent_win >> 1)  # do not play under an opponent threat


class _Solver:
    def __init__(self):
        self.nodes = 0
        self.table: dict[int, tuple[int, int]] = {}     # key -> (lower, upper) bounds

    def negamax(self, pos: int, mask: int, nb: int, alpha: int, beta: int) -> int:
        self.nodes += 1
        if _winning_cells(pos, mask) & ((mask + BOTTOM_MASK) & BOARD_MASK):
            return (SIZE + 1 - nb) // 2
        possible = _non_losing_moves(pos, mask)
        if possible == 0:
            return -((SIZE - nb) // 2)
        if nb >= SIZE - 2:
            return 0
        lo = -((SIZE - 2 - nb) // 2)
        if alpha < lo:
            alpha = lo
            if alpha >= beta:
                return alpha
        hi = (SIZE - 1 - nb) // 2
        if beta > hi:
            beta = hi
            if alpha >= beta:
                return beta
        key = pos + mask
        bounds = self.table.get(key)
        if bounds is not None:
            lower, upper = bounds
            if lower >= beta:
                return lower
            if upper <= alpha:
                return upper
            alpha = max(alpha, lower)
            beta = min(beta, upper)
        else:
            lower, upper = lo, hi

        alpha0 = alpha
        moves = []
        for col in CENTER_FIRST:
            move = possible & _col_mask(col)
            if move:
                threats = _winning_cells(pos | move, mask | move).bit_count()
                moves.append((threats, move))
        moves.sort(key=lambda t: -t[0])                  # stable: centre stays first on ties

        best = -SIZE
        for _, move in moves:
            score = -self.negamax(pos ^ mask, mask | move, nb + 1, -beta, -alpha)
            if score > best:
                best = score
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        break
        if best <= alpha0:
            upper = min(upper, best)
        elif best >= beta:
            lower = max(lower, best)
        else:
            lower = upper = best
        self.table[key] = (lower, upper)
        return best


def _solve_python(board: Board, weak: bool) -> int:
    pos, mask, nb = board.position, board.mask, board.num_moves
    s = _Solver()
    if weak:
        r = s.negamax(pos, mask, nb, -1, 1)      # fail-soft: only the sign is reliable
        return (r > 0) - (r < 0)
    low, high = -((SIZE - nb) // 2), (SIZE + 1 - nb) // 2
    while low < high:                      # narrow the window by binary search
        mid = low + (high - low) // 2
        if mid <= 0 and low // 2 < mid:
            mid = low // 2
        elif mid >= 0 and high // 2 > mid:
            mid = high // 2
        r = s.negamax(pos, mask, nb, mid, mid + 1)
        if r <= mid:
            high = r
        else:
            low = r
    return low


def _solve_binary(moves: str, weak: bool) -> int:
    exe = os.environ["C4_SOLVER_BIN"]
    cmd = [exe] + (["-w"] if weak else [])
    out = subprocess.run(cmd, input=moves + "\n", capture_output=True, text=True,
                         timeout=600, check=True).stdout.split()
    return int(out[1])


def solve(position, weak: bool = False) -> int:
    """Exact score of a position for the player to move (see the module docstring).

    weak=True only tells win / draw / loss (+1 / 0 / -1): much faster."""
    if isinstance(position, str):
        board = Board.from_moves(position)
        moves = position
    else:
        board, moves = position, None
    if board.is_over():
        raise ValueError("cannot solve a finished game")
    if moves is not None and os.environ.get("C4_SOLVER_BIN"):
        return _solve_binary(moves, weak)
    return _solve_python(board, weak)


def outcome(position) -> int:
    """+1 the player to move wins, 0 draw, -1 loses (perfect play)."""
    s = solve(position, weak=True)
    return (s > 0) - (s < 0)


def move_scores(board: Board) -> dict[int, int]:
    """Exact score of every legal move, from the point of view of the player who plays it.
    A winning move gets the maximum score for that position."""
    out = {}
    for col in board.legal_moves():
        if board.wins_by_playing(col):
            out[col] = (SIZE + 1 - board.num_moves) // 2
        else:
            out[col] = -solve(board.play_unchecked(col))
    return out


def best_moves(board: Board) -> list[int]:
    """All columns that keep the perfect-play result (ties included)."""
    scores = move_scores(board)
    top = max(scores.values())
    return [c for c, s in scores.items() if s == top]
