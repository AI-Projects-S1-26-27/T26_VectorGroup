"""Tests for eval/match.py and eval/stats.py.                         OWNER: Mani"""
import json

import pytest

from c4.board import Board
from eval import match
from eval.stats import bootstrap_mean_ci, sign_flip_pvalue, wilson


def test_openings_are_legal_unfinished_and_repeatable():
    a = match.make_openings(20, seed=1)
    assert a == match.make_openings(20, seed=1)
    assert a != match.make_openings(20, seed=2)
    for o in a:
        assert 2 <= len(o) <= 8
        assert not Board.from_moves(o).is_over()


def cfg(**kw):
    base = dict(a="heuristic", a_model=None, b="heuristic", b_model=None, games=4,
                time_limit=5.0, depth=2, workers=1, seed=0)
    base.update(kw)
    return base


def test_every_opening_is_played_twice_with_colours_swapped():
    result = match.run(cfg(), quiet=True)
    rows = result["rows"]
    assert len(rows) == 4
    by_opening = {}
    for r in rows:
        by_opening.setdefault(r["opening"], []).append(r["a_first"])
    assert all(sorted(v) == [0, 1] for v in by_opening.values())


def test_identical_players_score_exactly_half():
    # same deterministic engine on both sides and colours swapped on every opening
    s = match.run(cfg(games=6), quiet=True)["summary"]
    assert s["games"] == 6
    assert s["a_wins"] + s["draws"] + s["b_wins"] == 6
    assert s["a_score"] == pytest.approx(0.5)
    assert s["target_met"] is False


def test_summary_counts_and_target():
    rows = [dict(opening="1", winner="A"), dict(opening="1", winner="A"),
            dict(opening="2", winner="A"), dict(opening="2", winner="draw"),
            dict(opening="3", winner="B"), dict(opening="3", winner="A")]
    s = match.summarise(rows)
    assert (s["a_wins"], s["draws"], s["b_wins"]) == (4, 1, 1)
    assert s["a_score"] == pytest.approx(4.5 / 6)
    assert s["target_met"] is True
    assert s["a_win_rate_excluding_draws"] == pytest.approx(4 / 5)
    lo, hi = s["a_score_wilson95"]
    assert lo < s["a_score"] < hi


def test_save_writes_csv_and_json(tmp_path):
    result = match.run(cfg(), quiet=True)
    match.save(result, str(tmp_path / "x" / "run"))
    assert (tmp_path / "x" / "run.csv").exists()
    assert json.loads((tmp_path / "x" / "run.json").read_text())["games"] == 4


def test_cli_rejects_odd_game_count():
    with pytest.raises(SystemExit):
        match.main(["--games", "5"])


def test_wilson_interval():
    lo, hi = wilson(55, 100)
    assert 0.44 < lo < 0.55 < hi < 0.65
    assert wilson(0, 0) == (0.0, 1.0)
    lo, hi = wilson(100, 100)
    assert hi == pytest.approx(1.0) and lo > 0.95


def test_bootstrap_and_sign_flip():
    lo, hi = bootstrap_mean_ci([1, 1, 1, 1], n_boot=200)
    assert lo == hi == 1
    assert sign_flip_pvalue([1.0] * 12, n_perm=2000) < 0.01
    assert sign_flip_pvalue([1, -1, 1, -1, 1, -1], n_perm=2000) > 0.5
