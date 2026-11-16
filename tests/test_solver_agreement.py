"""Tests for eval/solver_agreement.py.                                OWNER: Mani"""
import pytest

from c4.board import Board
from eval import solver_agreement as sa


def test_sampled_positions_are_distinct_unfinished_and_in_range():
    ps = sa.sample_positions(15, seed=0, min_ply=16, max_ply=24)
    assert len(ps) == len(set(ps)) == 15
    keys = set()
    for p in ps:
        b = Board.from_moves(p)
        assert 16 <= b.num_moves <= 24 and not b.is_over()
        assert not ({b.key(), b.mirrored().key()} & keys)      # no mirror duplicates
        keys |= {b.key(), b.mirrored().key()}


def test_excluded_positions_never_appear():
    first = sa.sample_positions(10, seed=1, min_ply=16, max_ply=22)
    banned = set()
    for p in first:
        b = Board.from_moves(p)
        banned |= {b.key(), b.mirrored().key()}
    again = sa.sample_positions(10, seed=1, min_ply=16, max_ply=22, exclude_keys=banned)
    for p in again:
        assert Board.from_moves(p).key() not in banned


def test_bad_ply_range_is_rejected():
    with pytest.raises(ValueError):
        sa.sample_positions(1, min_ply=20, max_ply=10)


def test_accuracy_arithmetic():
    rows = [dict(ply=20, solver_outcome=1, net_score=300),     # right
            dict(ply=20, solver_outcome=-1, net_score=50),     # wrong
            dict(ply=24, solver_outcome=-1, net_score=-10),    # right
            dict(ply=30, solver_outcome=0, net_score=20)]      # draw, inside the band
    res = sa.evaluate_agreement(rows, ["net"], draw_band=100)["net"]
    assert res["decisive_positions"] == 3
    assert res["decisive_accuracy"] == pytest.approx(2 / 3)
    # three-class: row1 right, row2 predicted draw -> wrong, row3 draw -> wrong, row4 right
    assert res["three_class_accuracy"] == pytest.approx(2 / 4)
    buckets = sa.by_ply_bucket(rows, ["net"])
    assert buckets["18-23"]["n"] == 2 and buckets["18-23"]["net"] == pytest.approx(0.5)


def test_end_to_end_with_the_hand_written_evaluator():
    rows, summary = sa.run(8, ["heuristic"], None, seed=3, min_ply=20, max_ply=28,
                           exclude_data=None, workers=1, draw_band=100, quiet=True)
    assert len(rows) == 8 and summary["positions"] == 8
    assert sum(summary["solver_outcome_counts"].values()) == 8
    assert 0 <= summary["evaluators"]["heuristic"]["decisive_accuracy"] <= 1
    for r in rows:
        assert r["solver_outcome"] == (r["solver_score"] > 0) - (r["solver_score"] < 0)
