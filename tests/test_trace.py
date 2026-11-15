"""Tests for the score helpers and SearchTrace in c4/trace.py."""
from c4.board import Board
from c4.trace import (WIN_SCORE, MAX_HEURISTIC, MoveInfo, SearchTrace,
                      is_decided, plies_to_end, own_moves_to_win)


def test_is_decided():
    assert is_decided(WIN_SCORE - 7)          # forced win
    assert is_decided(-(WIN_SCORE - 3))       # forced loss
    assert not is_decided(0)                  # draw / unclear
    assert not is_decided(MAX_HEURISTIC)      # best possible heuristic guess


def test_plies_and_moves_to_win():
    assert plies_to_end(WIN_SCORE - 7) == 7
    assert plies_to_end(-(WIN_SCORE - 7)) == 7
    assert own_moves_to_win(WIN_SCORE - 1) == 1     # win right now
    assert own_moves_to_win(WIN_SCORE - 3) == 2
    assert own_moves_to_win(WIN_SCORE - 7) == 4


def test_trace_score_and_ranking():
    moves = {
        2: MoveInfo(col=2, score=10, depth=6, pv=[2]),
        3: MoveInfo(col=3, score=50, depth=6, pv=[3]),
        4: MoveInfo(col=4, score=-20, depth=6, pv=[4]),
    }
    t = SearchTrace(board=Board.empty(), chosen=3, depth=6, nodes=1000,
                    time_s=0.5, evaluator="heuristic", static_score=0, moves=moves)
    assert t.score == 50
    assert [m.col for m in t.ranked()] == [3, 2, 4]