import pytest

from c4.board import Board
from c4.search import search
from c4.trace import WIN_SCORE


class ZeroEvaluator:
    """Says every position is equal, so only real wins and losses matter."""
    name = "zero"

    def evaluate(self, board):
        return 0


class DictTT:
    """Tiny transposition table with the interface search expects."""
    def __init__(self):
        self.d = {}

    def probe(self, key):
        return self.d.get(key)

    def store(self, key, depth, value, flag, best_move):
        old = self.d.get(key)
        if old is None or depth >= old[0]:
            self.d[key] = (depth, value, flag, best_move)


EV = ZeroEvaluator()


def test_takes_immediate_win():
    t = search(Board.from_moves("121212"), EV, time_limit=1.0)   # X has 3 stacked in col 1
    assert t.chosen == 0
    assert t.score == WIN_SCORE - 1


def test_blocks_immediate_threat():
    b = Board.from_moves("12121")        # O to move; X threatens to win in column 1
    t = search(b, EV, time_limit=1.0)
    assert t.chosen == 0                 # O must block column 1
    assert t.moves[3].score == -(WIN_SCORE - 2)   # any other move loses in 2 plies


def test_finds_double_threat_win():
    b = Board.from_moves("3747")         # X has c3,c4 on the bottom row, X to move
    t = search(b, EV, time_limit=2.0)
    assert t.score == WIN_SCORE - 3      # win with X's 2nd move from now
    assert t.chosen in (1, 4)            # columns 2 or 5 make an open three
    assert t.moves[t.chosen].pv[0] == t.chosen
    assert len(t.moves[t.chosen].pv) == 3


def test_trace_covers_all_legal_moves():
    b = Board.from_moves("4453")
    t = search(b, EV, time_limit=0.3)
    assert sorted(t.moves) == b.legal_moves()
    assert t.depth >= 1 and t.nodes > 0
    assert all(m.pv[0] == m.col and m.exact for m in t.moves.values())
    assert t.chosen == max(t.moves, key=lambda c: (t.moves[c].score, -abs(c - 3)))


def test_respects_time_limit():
    t = search(Board.empty(), EV, time_limit=0.3)
    assert t.time_s < 1.5
    assert t.depth >= 1


def test_table_gives_same_forced_win_scores():
    b = Board.from_moves("3747")
    plain = search(b, EV, time_limit=2.0)
    with_tt = search(b, EV, time_limit=2.0, tt=DictTT())
    assert with_tt.score == plain.score == WIN_SCORE - 3


def test_table_gives_same_block_scores():
    b = Board.from_moves("12121")
    t = search(b, EV, time_limit=1.0, tt=DictTT())
    assert t.chosen == 0
    assert t.moves[3].score == -(WIN_SCORE - 2)


def test_finished_game_rejected():
    with pytest.raises(ValueError):
        search(Board.from_moves("1212121"), EV)


class CentreEvaluator:
    """Crude but non-trivial scorer: stones near the centre are worth more."""
    name = "centre"

    def evaluate(self, board):
        a = board.to_array()
        return sum(int(a[r, c]) * (4 - abs(c - 3)) for r in range(6) for c in range(7))


def plain_negamax(board, depth, ply):
    """Reference search with NO pruning, same scoring rules as search()."""
    moves = board.legal_moves()
    if not moves:
        return 0
    if any(board.wins_by_playing(c) for c in moves):
        return WIN_SCORE - (ply + 1)
    if depth == 0:
        return CentreEvaluator().evaluate(board)
    return max(-plain_negamax(board.play_unchecked(c), depth - 1, ply + 1) for c in moves)


def test_alpha_beta_matches_plain_minimax():
    import random
    rng = random.Random(5)
    checked = 0
    while checked < 25:
        b = Board.empty()
        for _ in range(rng.randint(0, 18)):
            if b.is_over():
                break
            b = b.play(rng.choice(b.legal_moves()))
        if b.is_over():
            continue
        t = search(b, CentreEvaluator(), time_limit=30.0, max_depth=4)
        for c, info in t.moves.items():
            if b.wins_by_playing(c):
                expected = WIN_SCORE - 1
            else:
                expected = -plain_negamax(b.play_unchecked(c), t.depth - 1, 1)
            assert info.score == expected, (b.render(), c, t.depth)
        checked += 1