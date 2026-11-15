import random

from c4.board import Board
from c4.eval_heuristic import HeuristicEvaluator, WINDOWS
from c4.trace import MAX_HEURISTIC

EV = HeuristicEvaluator()


def test_empty_and_windows():
    assert EV.name == "heuristic"
    assert EV.evaluate(Board.empty()) == 0
    assert len(WINDOWS) == len(set(WINDOWS)) == 69
    assert all(w.bit_count() == 4 for w in WINDOWS)


def test_centre_and_threats():
    assert EV.evaluate(Board.from_moves("4")) < EV.evaluate(Board.from_moves("1"))
    assert EV.evaluate(Board.from_moves("121213")) > 0
    assert EV.evaluate(Board.from_moves("12121")) < 0


def test_bounds_symmetry_and_no_mutation():
    rng = random.Random(26)
    for _ in range(60):
        board = Board.empty()
        for _ in range(rng.randrange(35)):
            if board.is_over():
                break
            board = board.play(rng.choice(board.legal_moves()))
        if board.is_over():
            continue
        before = (board.position, board.mask)
        score = EV.evaluate(board)
        assert type(score) is int and abs(score) <= MAX_HEURISTIC
        assert EV.evaluate(board.mirrored()) == score
        assert EV.evaluate(Board(board.position ^ board.mask, board.mask)) == -score
        assert (board.position, board.mask) == before

