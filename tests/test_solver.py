"""Tests for eval/solver.py.                                          OWNER: Mani"""
import random

import pytest

from c4.board import SIZE, Board
from eval.solver import best_moves, move_scores, outcome, solve


def brute_force(board, alpha=-99, beta=99):
    """Plain alpha-beta over the whole game, no solver tricks: the reference answer."""
    nb = board.num_moves
    moves = board.legal_moves()
    if not moves:
        return 0
    for c in moves:
        if board.wins_by_playing(c):
            return (SIZE + 1 - nb) // 2
    best = -99
    for c in moves:
        best = max(best, -brute_force(board.play_unchecked(c), -beta, -alpha))
        alpha = max(alpha, best)
        if alpha >= beta:
            break
    return best


def late_positions(n, seed, plies=(29, 30, 31, 32)):
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        b = Board.empty()
        target = rng.choice(plies)
        while b.num_moves < target and not b.is_over():
            b = b.play(rng.choice(b.legal_moves()))
        if not b.is_over():
            out.append(b)
    return out


def test_immediate_win_scores_the_maximum():
    # X has 1,2,3 on the bottom row and is to move: wins with its 4th stone -> 22 - 4
    assert solve("112233") == 18
    assert outcome("112233") == 1


def test_matches_brute_force_on_late_positions():
    for b in late_positions(12, seed=3):
        assert solve(b) == brute_force(b)


def test_weak_solve_has_the_same_sign_as_the_exact_score():
    for b in late_positions(12, seed=4):
        s = solve(b)
        assert solve(b, weak=True) == (s > 0) - (s < 0)
        assert outcome(b) == (s > 0) - (s < 0)


def test_mirror_image_has_the_same_score():
    for b in late_positions(6, seed=5):
        assert solve(b) == solve(b.mirrored())


def test_move_string_and_board_give_the_same_answer():
    moves = "44435322"
    assert solve(moves) == solve(Board.from_moves(moves))


def test_move_scores_agree_with_the_position_score():
    for b in late_positions(6, seed=6, plies=(30, 31, 32)):
        scores = move_scores(b)
        assert set(scores) == set(b.legal_moves())
        assert max(scores.values()) == solve(b)
        assert all(scores[c] == solve(b) for c in best_moves(b))


def test_finished_game_is_rejected():
    with pytest.raises(ValueError):
        solve("1212121")          # first player already has four in column 1
