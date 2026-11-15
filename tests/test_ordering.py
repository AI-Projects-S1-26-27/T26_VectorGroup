from collections import Counter

import pytest

from c4.board import Board, CENTER_FIRST
from c4.ordering import move_ordering


def test_centre_order_and_input_preserved():
    moves = list(range(7))
    assert move_ordering(Board.empty(), moves, None) == list(CENTER_FIRST)
    assert moves == list(range(7))


def test_win_block_and_tt_priorities():
    winning = Board.from_moves("121212")
    assert move_ordering(winning, winning.legal_moves(), None)[0] == 0
    assert move_ordering(winning, winning.legal_moves(), 6)[0] == 6
    blocking = Board.from_moves("12121")
    assert move_ordering(blocking, blocking.legal_moves(), None)[0] == 0


@pytest.mark.parametrize("moves,tt_move", [([], 3), ([6, 0], 3), ([3, 3, 0], 0)])
def test_preserves_exact_move_multiset(moves, tt_move):
    assert Counter(move_ordering(Board.empty(), moves, tt_move)) == Counter(moves)


def test_full_column_and_board_unchanged():
    board = Board.from_moves("444444")
    before = (board.position, board.mask)
    ordered = move_ordering(board, board.legal_moves(), 3)
    assert 3 not in ordered
    assert Counter(ordered) == Counter(board.legal_moves())
    assert (board.position, board.mask) == before
