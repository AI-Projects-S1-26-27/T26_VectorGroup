import pytest

from c4.board import Board
from c4.eval_heuristic import HeuristicEvaluator
from c4.ordering import move_ordering
from c4.search import search
from c4.tt import TranspositionTable
from eval.node_counts import compare_node_counts, main
from eval.node_counts import fixed_positions
from eval.node_counts import summarize_node_counts


def test_summary_excludes_short_runs_and_detects_score_mismatch():
    rows = []
    for position, completed, score in (("", 8, 0), ("1", 3, 99997), ("2", 7, 0)):
        for config, nodes in (("baseline", 100), ("ordering", 80),
                              ("tt", 60), ("tt+ordering", 50)):
            rows.append(dict(position=position, configuration=config,
                             requested_depth=8, completed_depth=completed,
                             score=score, nodes=nodes, time_s=0.1))
    result = summarize_node_counts(rows)
    assert result["full_depth_positions"] == 1
    assert result["early_decided_positions"] == result["incomplete_positions"] == 1
    assert result["aggregate_node_reduction"] == result["median_position_reduction"] == 2
    assert result["total_nodes"]["baseline"] == 100
    assert result["target_met"] is False
    assert result["score_mismatch_positions"] == []
    rows[0]["score"] = 123
    assert summarize_node_counts(rows)["score_mismatch_positions"] == [""]
    with pytest.raises(ValueError):
        summarize_node_counts(rows[:-1])


def test_fixed_positions_reproducible_unique_and_nontrivial():
    positions = fixed_positions()
    assert positions == fixed_positions(seed=26)
    assert positions != fixed_positions(seed=27)
    boards = [Board.from_moves(moves) for moves in positions]
    assert len(boards) == len({b.key() for b in boards}) == 100
    assert all(not b.is_over() and not b.winning_moves() for b in boards)
    assert min(map(len, positions)) == 0
    assert max(map(len, positions)) == 24


def test_csv_file_output(tmp_path):
    import csv
    import json
    target = tmp_path / "nested" / "nodes.csv"
    summary = tmp_path / "summary.json"
    main(["--depth", "1", "--count", "2", "--out", str(target),
          "--summary", str(summary)])
    with target.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 8
    assert all(int(row["requested_depth"]) == 1 for row in rows)
    assert json.loads(summary.read_text())["full_depth_positions"] == 2


def test_comparison_at_equal_depth():
    rows = compare_node_counts(("4453",), depth=3)
    assert [r["configuration"] for r in rows] == ["baseline", "ordering", "tt", "tt+ordering"]
    assert all(r["completed_depth"] == 3 and r["nodes"] > 0 for r in rows)
    assert len({r["score"] for r in rows}) == 1


def test_parallel_positions_preserve_scores_and_nodes():
    positions = ("4453", "12121")
    serial = compare_node_counts(positions, depth=2)
    parallel = compare_node_counts(positions, depth=2, workers=2)
    fields = ("position", "configuration", "nodes", "completed_depth", "score", "chosen")
    assert [[r[k] for k in fields] for r in serial] == [
        [r[k] for k in fields] for r in parallel]


@pytest.mark.parametrize("moves", ["", "4453", "12121", "3747"])
def test_hooks_preserve_every_root_score(moves):
    board = Board.from_moves(moves)
    plain = search(board, HeuristicEvaluator(), max_depth=4, time_limit=30)
    table = TranspositionTable()
    hooked = search(board, HeuristicEvaluator(), max_depth=4, time_limit=30,
                    tt=table, order_fn=move_ordering)
    assert hooked.depth == plain.depth
    assert hooked.chosen == plain.chosen
    assert {c: m.score for c, m in hooked.moves.items()} == {
        c: m.score for c, m in plain.moves.items()}
    # Repeat with a warm table to exercise cached bounds and exact values.
    warm = search(board, HeuristicEvaluator(), max_depth=4, time_limit=30,
                  tt=table, order_fn=move_ordering)
    assert {c: m.score for c, m in warm.moves.items()} == {
        c: m.score for c, m in plain.moves.items()}


def test_invalid_benchmark_inputs():
    with pytest.raises(ValueError):
        compare_node_counts(depth=0)
    with pytest.raises(ValueError):
        compare_node_counts(time_limit=0)
    with pytest.raises(ValueError):
        compare_node_counts(("1212121",))


def test_csv_cli(capsys):
    main(["--depth", "1", "--positions", "4453"])
    output = capsys.readouterr().out
    assert "configuration" in output and "tt+ordering" in output
