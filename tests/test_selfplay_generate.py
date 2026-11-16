import json

import numpy as np
import pytest

from c4.board import Board
from c4.selfplay import generate as gen
from c4.selfplay.generate import SelfPlayConfig, play_game, run, NO_SCORE


class ZeroEvaluator:
    """Every position is equal, so only real wins and losses matter. Fast."""
    name = "zero"

    def evaluate(self, board):
        return 0


SPEC = f"{__name__}:ZeroEvaluator"


def cfg(tmp_path, **kw):
    base = dict(games=12, round=0, evaluator=SPEC, depth=2, games_per_shard=5,
                out_dir=str(tmp_path), workers=1)
    base.update(kw)
    return SelfPlayConfig(**base)


def test_game_is_legal_and_labelled_correctly(tmp_path):
    c = cfg(tmp_path)
    g = play_game(c, 3, ZeroEvaluator())
    n = len(g["ply"])
    assert g["ply"] == list(range(n))                   # one row per move, from the empty board
    # replaying the stored moves gives the stored positions and a finished game
    b = Board.empty()
    for i in range(n):
        assert (b.position, b.mask) == (g["position"][i], g["mask"][i])
        b = b.play(g["move"][i])
    assert b.is_over()
    if g["winner"] is None:
        assert b.is_draw() and set(g["result"]) == {0}
    else:
        assert g["winner"] == (n - 1) % 2
        assert g["result"][-1] == 1                     # the player who made the last move won
        assert all(g["result"][i] == -g["result"][i + 1] for i in range(n - 1))


def test_random_opening_and_scores(tmp_path):
    c = cfg(tmp_path, min_random=3, max_random=3)
    g = play_game(c, 0, ZeroEvaluator())
    assert g["random"][:3] == [True] * 3
    assert all(s == NO_SCORE for s in g["score"][:3])
    assert not any(g["random"][3:])                     # epsilon = 0
    assert all(s != NO_SCORE for s in g["score"][3:])


def test_games_are_reproducible_and_varied(tmp_path):
    c = cfg(tmp_path)
    a, b = play_game(c, 7, ZeroEvaluator()), play_game(c, 7, ZeroEvaluator())
    assert a["move"] == b["move"]
    others = {tuple(play_game(c, i, ZeroEvaluator())["move"]) for i in range(8)}
    assert len(others) > 1


def test_engine_takes_a_win_it_can_see(tmp_path):
    # with no random moves after the opening, the engine never misses a win in 1
    c = cfg(tmp_path, min_random=0, max_random=4)
    for i in range(5):
        g = play_game(c, i, ZeroEvaluator())
        for pos, mask, move, rnd in zip(g["position"], g["mask"], g["move"], g["random"]):
            b = Board(pos, mask)
            if not rnd and b.winning_moves():
                assert b.wins_by_playing(move)


def test_run_writes_shards_meta_and_resumes(tmp_path):
    c = cfg(tmp_path)
    totals = run(c, quiet=True)
    rdir = c.round_dir()
    shards = sorted(rdir.glob("shard_?????.npz"))
    assert len(shards) == 3                              # 12 games, 5 per shard
    assert not list(rdir.glob("*.tmp.npz"))
    assert totals["games"] == 12
    assert totals["x_wins"] + totals["o_wins"] + totals["draws"] == 12
    meta = json.loads((rdir / "meta.json").read_text())
    assert meta["totals"] == totals and meta["settings"]["depth"] == 2
    with np.load(shards[0]) as z:
        assert set(z.files) == set(gen.SHARD_FIELDS)
        assert z["position"].dtype == np.uint64 and len(np.unique(z["game"])) == 5
    # running again skips finished shards
    before = [p.stat().st_mtime_ns for p in shards]
    assert run(c, quiet=True) == totals
    assert [p.stat().st_mtime_ns for p in shards] == before


def test_refuses_to_mix_settings(tmp_path):
    run(cfg(tmp_path, games=5), quiet=True)
    with pytest.raises(SystemExit):
        run(cfg(tmp_path, games=5, depth=3), quiet=True)


def test_parallel_matches_serial(tmp_path):
    a = cfg(tmp_path / "a", games=6, games_per_shard=3)
    b = cfg(tmp_path / "b", games=6, games_per_shard=3, workers=2)
    run(a, quiet=True)
    run(b, quiet=True)
    for s in range(2):
        with np.load(gen.shard_path(a, s)) as za, np.load(gen.shard_path(b, s)) as zb:
            for k in gen.SHARD_FIELDS:
                assert np.array_equal(za[k], zb[k])


def test_missing_evaluator_module_gives_clear_error():
    with pytest.raises(RuntimeError, match="not on this branch yet"):
        gen.make_evaluator("c4.does_not_exist:Nothing")


def test_network_needs_model():
    with pytest.raises((ValueError, RuntimeError)):
        gen.make_evaluator("network", None)


def test_cli_arguments():
    c, force = gen.parse_args(["--games", "10", "--round", "2", "--depth", "4",
                               "--workers", "1", "--no-tt"])
    assert (c.games, c.round, c.depth, c.use_tt, c.use_ordering, force) == (10, 2, 4, False, True, False)
