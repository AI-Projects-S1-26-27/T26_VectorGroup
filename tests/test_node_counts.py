import pytest

from c4.board import Board
from c4.eval_heuristic import HeuristicEvaluator
from c4.ordering import move_ordering
from c4.search import search
from c4.tt import TranspositionTable
from eval.node_counts import compare_node_counts, main
from eval.node_counts import fixed_positions
from eval.node_counts import summarize_node_counts
from eval.node_counts import fixed_depth_run, run_sweep, summarize_sweep
from eval.node_counts import build_native_minimax, native_minimax_run


@pytest.fixture(scope="module")
def native_counter():
    try:
        return build_native_minimax()
    except RuntimeError as error:
        pytest.skip(str(error))


@pytest.mark.parametrize("moves", ["", "4453", "12121", "3747", "444444"])
def test_native_minimax_matches_python_exact_nodes_and_all_scores(native_counter, moves):
    native = native_minimax_run(moves, 4, None, 30, native_counter)
    python = fixed_depth_run(moves, 4, "minimax", node_limit=None, time_limit=30)
    for field in ("status", "nodes", "chosen", "score", "root_scores", "completed_depth"):
        assert native[field] == python[field], (moves, field)


def test_native_minimax_limit_and_parallel_sweep(native_counter, tmp_path):
    limited = native_minimax_run("", 8, 10, 30, native_counter)
    assert limited["status"] == "node_limit" and limited["nodes"] == 10
    assert limited["score"] is limited["chosen"] is None and limited["root_scores"] == ""
    rows = run_sweep(("", "4453"), (2,), tmp_path / "native.csv", workers=2,
                     node_limit=None, native_executable=native_counter)
    assert summarize_sweep(rows)["fully_completed"]
    assert summarize_sweep(rows)["scores_consistent"]
    assert {r["backend"] for r in rows} == {"native_minimax", "python"}


def test_minimax_counts_full_tree_without_alpha_beta_or_table():
    # No wins before depth 2: 7 root children and 49 grandchildren, root excluded.
    row = fixed_depth_run("", 2, "minimax")
    assert row["status"] == "complete" and row["nodes"] == 7 + 49
    assert row["tt_hits"] == 0


@pytest.mark.parametrize("moves", ["", "4453", "12121", "3747"])
def test_fixed_depth_algorithms_match_all_root_scores(moves):
    import json
    rows = [fixed_depth_run(moves, 4, c, node_limit=None, time_limit=30)
            for c in ("minimax", "alpha-beta", "alpha-beta+ordering+tt")]
    assert all(r["status"] == "complete" and r["completed_depth"] == 4 for r in rows)
    assert len({r["root_scores"] for r in rows}) == 1
    assert len({r["chosen"] for r in rows}) == 1
    # Independent production iterative search, using its actual last depth.
    trace = search(Board.from_moves(moves), HeuristicEvaluator(), max_depth=4, time_limit=30)
    at_trace_depth = fixed_depth_run(moves, trace.depth, "minimax", node_limit=None)
    assert {int(k): v for k, v in json.loads(at_trace_depth["root_scores"]).items()} == {
        c: info.score for c, info in trace.moves.items()}


@pytest.mark.parametrize("configuration", ["minimax", "alpha-beta", "alpha-beta+ordering+tt"])
def test_limited_run_does_not_publish_partial_scores(configuration):
    row = fixed_depth_run("", 4, configuration, node_limit=10)
    assert row["status"] == "node_limit" and row["nodes"] == 10
    assert row["completed_depth"] == 0
    assert row["score"] is row["chosen"] is None
    assert row["root_scores"] == ""


def test_time_limited_run_is_not_a_completed_measurement():
    row = fixed_depth_run("", 12, "minimax", node_limit=None, time_limit=1e-12)
    assert row["status"] == "time_limit"
    assert row["nodes"] == 0 and row["completed_depth"] == 0
    assert row["score"] is None and row["root_scores"] == ""


def test_sweep_checkpoints_resumes_and_groups_depths(tmp_path):
    import csv
    with pytest.raises(ValueError, match="empty sweep"):
        summarize_sweep([])
    target = tmp_path / "sweep.csv"
    rows = run_sweep(("", "4453"), (1, 2), target, workers=2, node_limit=20)
    assert len(rows) == 12
    summary = summarize_sweep(rows)
    assert summary["scores_consistent"]
    assert summary["proposal_depth8_target"]["status"] == "not_fully_measured"
    assert summary["depths"]["1"]["complete"]["minimax"] == 2
    assert summary["depths"]["2"]["paired_comparisons"]["minimax"]["positions"] == 0
    assert summary["depths"]["2"]["paired_comparisons"]["minimax"]["reduction"] is None
    inconsistent = [dict(row) for row in rows]
    inconsistent[0]["root_scores"] = "{}"
    assert not summarize_sweep(inconsistent)["scores_consistent"]
    assert summarize_sweep(inconsistent)["depths"]["1"]["all_complete_positions"] == 1
    # Simulate interruption after one saved job and resume without duplication.
    with target.open(encoding="utf-8", newline="") as stream:
        saved = list(csv.DictReader(stream))
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=saved[0])
        writer.writeheader()
        writer.writerow(saved[0])
    resumed = run_sweep(("", "4453"), (1, 2), target, node_limit=20, resume=True)
    assert len(resumed) == 12
    assert summarize_sweep(resumed) == summary
    with pytest.raises(ValueError, match="does not match"):
        run_sweep(("", "4453"), (1, 2), target, node_limit=21, resume=True)


def test_sweep_cli_writes_summary(tmp_path):
    import json
    main(["--depths", "1", "2", "--count", "2", "--workers", "2",
          "--out", str(tmp_path / "sweep.csv"), "--summary", str(tmp_path / "sweep.json")])
    summary = json.loads((tmp_path / "sweep.json").read_text())
    assert set(summary["depths"]) == {"1", "2"}
    assert summary["fully_completed"] and summary["scores_consistent"]


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
