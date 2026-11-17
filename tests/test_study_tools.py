"""Tests for the form generator, the form-CSV converter and the report tables.   OWNER: Mani"""
import csv
import json

from eval import report_tables as rt
from eval.match import Player
from eval.user_study import analyse_ratings as ar
from eval.user_study import build_study as bs
from eval.user_study import convert_form as cf
from eval.user_study import make_form_script as mf


def make_items(tmp_path, n=4):
    items = bs.build_items(n, seed=2, evaluator=Player("heuristic"), time_limit=0.05,
                           min_ply=8, max_ply=20)
    bs.save(items, str(tmp_path))
    return items


def test_every_study_item_has_a_different_agent_and_baseline_text(tmp_path):
    items = make_items(tmp_path)
    assert len(items) == 4
    assert all(i["agent_text"] != i["baseline_text"] for i in items)
    assert 0 < items[0]["explained_share"] <= 1


def test_form_script_contains_all_items_and_the_forms_api(tmp_path):
    items = make_items(tmp_path)
    js = mf.build_script(tmp_path / "items.csv")
    assert "FormApp.create" in js and "addScaleItem" in js and "setBounds(1, 5)" in js
    for it in items:
        assert it["agent_text"] in js or json.dumps(it["agent_text"], ensure_ascii=False)[1:-1] in js
        assert json.dumps(it["baseline_text"], ensure_ascii=False)[1:-1] in js


def test_converter_reads_google_form_columns_and_feeds_the_analysis(tmp_path):
    key = {s: {str(i): bs.condition(i, s) for i in range(1, 3)} for s in "AB"}
    header = ["Timestamp"] + [f"Item {i}: {d}" for i in (1, 2)
                              for d in ("Correctness", "Clarity", "Usefulness")]
    for sheet in "AB":
        with open(tmp_path / f"{sheet}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            for _ in range(3):
                row = ["2026/11/18"]
                for i in (1, 2):
                    agent = key[sheet][str(i)] == "agent"
                    row += [5, 4, 5] if agent else [3, 4, 2]
                w.writerow(row)
    rows, notes = cf.convert({"A": str(tmp_path / "A.csv"), "B": str(tmp_path / "B.csv")})
    assert len(rows) == 12 and not notes
    assert {r["rater"] for r in rows} == {"A1", "A2", "A3", "B1", "B2", "B3"}
    res = ar.analyse(rows, key)
    assert res["raters"] == 6
    assert abs(res["dimensions"]["correctness"]["mean_difference"] - 2.0) < 1e-9


def test_report_tables_marks_missing_experiments(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "R", tmp_path)          # empty results folder
    text = rt.build()
    assert text.count("NOT RUN YET") >= 5
    assert "## Results against the proposal's targets" in text
