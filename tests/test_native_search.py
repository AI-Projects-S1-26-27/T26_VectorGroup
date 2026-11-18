"""Rujuta's optional native-backend correctness and interoperability checks."""
import random

import pytest

from c4.board import Board
from c4.eval_heuristic import HeuristicEvaluator
from c4.native_search import NativeUnavailable, prepare_native_search
from c4.ordering import move_ordering
from c4.search import EXACT, LOWER, UPPER, search
from c4.tt import TranspositionTable


@pytest.fixture(scope="module")
def native_library():
    try:
        return prepare_native_search()
    except NativeUnavailable as error:
        if "needs g++" in str(error):
            pytest.skip(str(error))
        raise


@pytest.mark.parametrize("sequence", ["", "4453", "12121", "3747", "444444", "332432", "33243244152251"])
@pytest.mark.parametrize("use_hooks", [False, True])
def test_native_matches_python_every_root_score_and_node_count(native_library, sequence, use_hooks):
    board = Board.from_moves(sequence)
    traces = []
    for backend in ("python", "native"):
        traces.append(search(board, HeuristicEvaluator(), max_depth=4, time_limit=30,
                             tt=TranspositionTable() if use_hooks else None,
                             order_fn=move_ordering if use_hooks else None, backend=backend))
    python, native = traces
    assert native.depth == python.depth
    assert native.nodes == python.nodes
    assert native.chosen == python.chosen
    assert native.static_score == python.static_score
    assert {c: (m.score, m.pv) for c, m in native.moves.items()} == {
        c: (m.score, m.pv) for c, m in python.moves.items()}


def test_random_positions_and_warm_tables(native_library):
    rng = random.Random(18112026)
    evaluator = HeuristicEvaluator()
    for _ in range(15):
        board = Board.empty()
        for _ in range(rng.randrange(20)):
            if board.is_over():
                break
            board = board.play(rng.choice(board.legal_moves()))
        if board.is_over():
            continue
        assert native_library.c4_evaluate(board.position, board.mask) == evaluator.evaluate(board)
        reference = search(board, evaluator, max_depth=4, time_limit=30, backend="python")
        table = TranspositionTable()
        for _ in range(2):
            trace = search(board, evaluator, max_depth=4, time_limit=30,
                           tt=table, order_fn=move_ordering, backend="native")
            assert trace.depth == reference.depth
            assert {c: m.score for c, m in trace.moves.items()} == {
                c: m.score for c, m in reference.moves.items()}
            for move in trace.moves.values():
                state = board
                for col in move.pv:
                    assert not state.is_over() and col in state.legal_moves()
                    state = state.play(col)


def test_table_migration_public_api_capacity_and_clear(native_library):
    table = TranspositionTable(2)
    table.store(1, 4, 123, EXACT, 0)
    table.store(2, 2, -40, LOWER, None)
    assert table.probe(1) == (4, 123, EXACT, 0)
    before = table.stats()
    table.native_context()
    assert table.stats() == before
    assert table.probe(1) == (4, 123, EXACT, 0)
    table.store(1, 3, 999, EXACT, 3)
    table.store(1, 4, 999, UPPER, 3)
    assert table.probe(1) == (4, 123, EXACT, 0)
    table.store(3, 1, 50, EXACT, 6)
    assert len(table) == 2 and table.probe(1) is None
    assert table.probe(2) == (2, -40, LOWER, None)
    table.clear()
    assert table.stats() == dict(entries=0, probes=0, hits=0, stores=0)


def test_native_time_limit_and_finished_board(native_library):
    trace = search(Board.empty(), HeuristicEvaluator(), time_limit=0.05,
                   tt=TranspositionTable(), order_fn=move_ordering, backend="native")
    assert trace.depth >= 1 and trace.time_s < 0.5
    assert sorted(trace.moves) == list(range(7))
    with pytest.raises(ValueError):
        search(Board.from_moves("1212121"), HeuristicEvaluator(), backend="native")


def test_auto_falls_back_when_native_unavailable(monkeypatch):
    import c4.native_search as native
    def unavailable():
        raise NativeUnavailable("compiler unavailable")
    monkeypatch.setattr(native, "prepare_native_search", unavailable)
    trace = search(Board.empty(), HeuristicEvaluator(), max_depth=2, backend="auto")
    assert trace.depth == 2 and getattr(trace, "backend", "python") == "python"


def test_custom_evaluator_keeps_python_path(native_library, monkeypatch):
    class Zero:
        name = "zero"
        def evaluate(self, board):
            return 0
    monkeypatch.setenv("C4_SEARCH_BACKEND", "auto")
    assert search(Board.empty(), Zero(), max_depth=2).depth == 2
    with pytest.raises(ValueError, match="Custom"):
        search(Board.empty(), Zero(), max_depth=2, backend="native")
