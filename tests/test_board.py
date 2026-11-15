"""Board tests. The oracle is a slow, obviously-correct array-based win checker."""
import random

import pytest

from c4.board import Board, SIZE


def brute_has_four(arr) -> bool:
    for r in range(6):
        for c in range(7):
            v = arr[r, c]
            if v == 0:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                ok = True
                for k in range(1, 4):
                    rr, cc = r + dr * k, c + dc * k
                    if not (0 <= rr < 6 and 0 <= cc < 7) or arr[rr, cc] != v:
                        ok = False
                        break
                if ok:
                    return True
    return False


def test_empty():
    b = Board.empty()
    assert b.num_moves == 0 and b.player_to_move == 0
    assert b.legal_moves() == list(range(7))
    assert not b.is_over()


def test_vertical_win():
    b = Board.from_moves("1212121")
    assert b.last_mover_won() and b.is_over()


def test_horizontal_win():
    assert Board.from_moves("1122334").last_mover_won()


def test_diagonal_win_and_mirror():
    b = Board.from_moves("12234334744")
    assert b.last_mover_won()
    assert b.mirrored().last_mover_won()


def test_full_column():
    b = Board.from_moves("111111")
    assert not b.can_play(0)
    assert 0 not in b.legal_moves()
    with pytest.raises(ValueError):
        b.play(0)


def test_from_moves_rejects_illegal():
    with pytest.raises(ValueError):
        Board.from_moves("1111111")      # 7th stone in a column
    with pytest.raises(ValueError):
        Board.from_moves("12121212")     # plays after the game was won


def test_winning_moves():
    b = Board.from_moves("121212")       # X has three stacked in column 1
    assert b.winning_moves() == [0]
    assert b.wins_by_playing(0)


def test_render_shape():
    assert len(Board.from_moves("4453").render().splitlines()) == 7


def test_random_playouts_match_bruteforce():
    rng = random.Random(0)
    for _ in range(1500):
        b = Board.empty()
        while not b.is_over():
            legal = b.legal_moves()
            # winning_moves agrees with actually playing the move
            for c in legal:
                assert b.wins_by_playing(c) == b.play(c).last_mover_won()
            b = b.play(rng.choice(legal))
            arr = b.to_absolute()
            assert b.last_mover_won() == brute_has_four(arr)
            # absolute <-> board round trip
            assert Board.from_absolute(arr) == b
        assert b.num_moves <= SIZE
        if b.num_moves == SIZE and not b.last_mover_won():
            assert b.is_draw()


def test_mirror_involution_and_key():
    rng = random.Random(1)
    seen = {}
    for _ in range(300):
        b = Board.empty()
        for _ in range(rng.randint(0, 20)):
            if b.is_over():
                break
            b = b.play(rng.choice(b.legal_moves()))
        assert b.mirrored().mirrored() == b
        k = b.key()
        assert seen.setdefault(k, b) == b       # equal key => equal position


def test_to_array_perspective():
    b = Board.from_moves("4")                    # X played the centre column
    assert b.to_array()[0, 3] == -1              # O to move: X's stone is "opponent"
    assert b.to_absolute()[0, 3] == 1