import pytest

from c4.board import Board
from c4.eval_heuristic import HeuristicEvaluator
from c4.ordering import move_ordering
from c4.search import search
from c4.tt import TranspositionTable
from eval.node_counts import compare_node_counts, main


def test_comparison_at_equal_depth():
    rows = compare_node_counts(("4453",), depth=3)
    assert [r["configuration"] for r in rows] == ["baseline", "ordering", "tt", "tt+ordering"]
    assert all(r["completed_depth"] == 3 and r["nodes"] > 0 for r in rows)
    assert len({r["score"] for r in rows}) == 1


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
