"""Tests for eval/user_study/.                                        OWNER: Mani"""
import csv

import pytest

from c4.board import Board
from eval.match import Player
from eval.user_study import analyse_ratings as ar
from eval.user_study import build_study as bs


def test_sheets_are_exact_opposites():
    for item in range(1, 31):
        assert {bs.condition(item, "A"), bs.condition(item, "B")} == {"agent", "baseline"}
    assert sum(bs.condition(i, "A") == "agent" for i in range(1, 31)) == 15


def test_board_drawing_has_six_rows_plus_numbers():
    text = bs.board_emoji(Board.from_moves("4453"))
    assert len(text.splitlines()) == 7
    assert text.count("🔴") == 2 and text.count("🟡") == 2


def test_items_and_sheets(tmp_path):
    items = bs.build_items(4, seed=1, evaluator=Player("heuristic"), time_limit=0.05,
                           min_ply=6, max_ply=12, require_explanations=False)
    assert [i["item"] for i in items] == [1, 2, 3, 4]
    for it in items:
        b = Board.from_moves(it["moves"])
        assert b.can_play(it["chosen_col"] - 1) and it["agent_text"] and it["baseline_text"]
    bs.save(items, str(tmp_path))
    a = (tmp_path / "sheet_A.md").read_text(encoding="utf-8")
    b = (tmp_path / "sheet_B.md").read_text(encoding="utf-8")
    assert "Item 4" in a and a != b
    assert "agent" not in a.lower().split("program's move")[0]    # conditions are not revealed


def test_analysis_finds_a_known_difference(tmp_path):
    key = {"A": {str(i): bs.condition(i, "A") for i in range(1, 7)},
           "B": {str(i): bs.condition(i, "B") for i in range(1, 7)}}
    path = tmp_path / "r.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rater", "sheet", "item", "correctness", "clarity", "usefulness"])
        for rater in range(12):
            sheet = "AB"[rater % 2]
            for item in range(1, 7):
                agent = key[sheet][str(item)] == "agent"
                w.writerow([f"r{rater}", sheet, item, 5 if agent else 3, 4 if agent else 4,
                            4 if agent else 2])
    res = ar.analyse(ar.load_ratings(path), key)
    assert res["raters"] == 12
    d = res["dimensions"]
    assert d["correctness"]["mean_difference"] == pytest.approx(2.0)
    assert d["clarity"]["mean_difference"] == pytest.approx(0.0)
    assert d["usefulness"]["mean_difference"] == pytest.approx(2.0)
    assert d["correctness"]["sign_flip_p"] < 0.01
    assert d["clarity"]["sign_flip_p"] > 0.9


def test_out_of_range_rating_is_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("rater,sheet,item,correctness,clarity,usefulness\nr1,A,1,6,3,3\n")
    with pytest.raises(ValueError):
        ar.load_ratings(path)
