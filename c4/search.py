"""Negamax search with alpha-beta pruning inside iterative deepening.  

search() looks at the position for about `time_limit` seconds, searching one ply
deeper each round (iterative deepening), and returns a SearchTrace.

Key points
  * Negamax: one function for both players. A score is always from the point of
    view of the player TO MOVE, and the parent flips the sign:  score = -negamax(child).
  * Alpha-beta: skip branches that cannot change the result.
  * Every legal ROOT move is searched with a FULL window (-INF, +INF), so its
    score is exact. That is what lets us answer "why not column c?" later.
  * Wins are scored WIN_SCORE - plies, so a quicker win is better and a slower
    loss is better (see c4/trace.py).
  * Optional hooks (so Rujuta's parts plug in without touching this file):
      tt        object with probe(key) -> (depth, value, flag, best_move) | None
                and store(key, depth, value, flag, best_move); flags EXACT/LOWER/UPPER
      order_fn  order_fn(board, moves, tt_move) -> list of the same moves, best first
"""
from __future__ import annotations

import time

from c4.board import Board, CENTER_FIRST, SIZE
from c4.evaluator import Evaluator
from c4.trace import MoveInfo, SearchTrace, WIN_SCORE, is_decided

EXACT, LOWER, UPPER = 0, 1, 2        # transposition-table entry types
INF = WIN_SCORE + 1000


class _TimeUp(Exception):
    """Raised inside the search when the time budget is used up."""


def _to_tt(value: int, ply: int) -> int:
    """Win/loss scores contain the distance from the ROOT. Before storing them in the
    table, make them relative to the node itself, so they stay correct when the same
    position is reached at a different depth."""
    if value > WIN_SCORE - SIZE - 1:
        return value + ply
    if value < -(WIN_SCORE - SIZE - 1):
        return value - ply
    return value


def _from_tt(value: int, ply: int) -> int:
    if value > WIN_SCORE - SIZE - 1:
        return value - ply
    if value < -(WIN_SCORE - SIZE - 1):
        return value + ply
    return value


class _Searcher:
    def __init__(self, evaluator: Evaluator, tt, order_fn):
        self.evaluator = evaluator
        self.tt = tt
        self.order_fn = order_fn
        self.nodes = 0
        self.deadline = float("inf")
        self.pv = [[] for _ in range(SIZE + 2)]   # pv[ply] = best line from that node

    def negamax(self, board: Board, depth: int, alpha: int, beta: int, ply: int) -> int:
        self.nodes += 1
        if self.nodes & 1023 == 0 and time.perf_counter() > self.deadline:
            raise _TimeUp
        self.pv[ply] = []

        moves = [c for c in CENTER_FIRST if board.can_play(c)]
        if not moves:
            return 0                                    # board full: draw
        for c in moves:                                 # can the mover win right now?
            if board.wins_by_playing(c):
                self.pv[ply] = [c]
                return WIN_SCORE - (ply + 1)
        if depth == 0:
            return self.evaluator.evaluate(board)       # horizon: guess the position

        alpha_orig = alpha
        key = board.key()
        tt_move = None
        if self.tt is not None:
            entry = self.tt.probe(key)
            if entry is not None:
                e_depth, e_value, e_flag, e_move = entry
                tt_move = e_move
                # no table cut-offs next to the root, so root moves stay exact
                if e_depth >= depth and ply > 1:
                    value = _from_tt(e_value, ply)
                    if e_flag == EXACT:
                        return value
                    if e_flag == LOWER:
                        alpha = max(alpha, value)
                    else:
                        beta = min(beta, value)
                    if alpha >= beta:
                        return value

        if self.order_fn is not None:
            moves = self.order_fn(board, moves, tt_move)
        elif tt_move is not None and tt_move in moves:
            moves.remove(tt_move)
            moves.insert(0, tt_move)

        best = -INF
        best_move = None
        for c in moves:
            score = -self.negamax(board.play_unchecked(c), depth - 1, -beta, -alpha, ply + 1)
            if score > best:
                best = score
                best_move = c
                if score > alpha:
                    alpha = score
                    self.pv[ply] = [c] + self.pv[ply + 1]
                    if alpha >= beta:
                        break                           # beta cut-off

        if self.tt is not None:
            if best <= alpha_orig:
                flag = UPPER
            elif best >= beta:
                flag = LOWER
            else:
                flag = EXACT
            self.tt.store(key, depth, _to_tt(best, ply), flag, best_move)
        return best


def search(board: Board, evaluator: Evaluator, time_limit: float = 1.0,
           max_depth: int = 42, tt=None, order_fn=None) -> SearchTrace:
    if board.is_over():
        raise ValueError("cannot search a finished game")

    start = time.perf_counter()
    s = _Searcher(evaluator, tt, order_fn)
    static_score = evaluator.evaluate(board)
    root_moves = [c for c in CENTER_FIRST if board.can_play(c)]
    last_depth = min(max_depth, SIZE - board.num_moves)

    infos: dict[int, MoveInfo] = {}
    done_depth = 0
    for depth in range(1, last_depth + 1):
        if depth > 1 and time.perf_counter() - start > time_limit:
            break
        # depth 1 always finishes, so there is always a move to play
        s.deadline = float("inf") if depth == 1 else start + time_limit
        try:
            current: dict[int, MoveInfo] = {}
            for c in root_moves:
                if board.wins_by_playing(c):
                    current[c] = MoveInfo(col=c, score=WIN_SCORE - 1, depth=depth, pv=[c])
                    continue
                child = board.play_unchecked(c)
                score = -s.negamax(child, depth - 1, -INF, INF, 1)   # full window
                current[c] = MoveInfo(col=c, score=score, depth=depth, pv=[c] + s.pv[1])
        except _TimeUp:
            break                                       # throw away the unfinished round
        infos, done_depth = current, depth
        if is_decided(max(m.score for m in infos.values())):
            break                                       # proven result, no need to go deeper

    chosen = max(root_moves, key=lambda c: infos[c].score)   # ties: centre first
    return SearchTrace(
        board=board, chosen=chosen, depth=done_depth, nodes=s.nodes,
        time_s=time.perf_counter() - start, evaluator=evaluator.name,
        static_score=static_score, moves={c: infos[c] for c in sorted(infos)})