
from c4.eval_heuristic import HeuristicEvaluator
from c4.ordering import move_ordering
from c4.tt import TranspositionTable
from c4.search import search
from c4.board import Board


def test_search_integration():
    board = Board.empty()
    evaluator = HeuristicEvaluator()
    tt = TranspositionTable()

    trace = search(
        board,
        evaluator,
        time_limit=1.0,
        tt=tt,
        order_fn=move_ordering,
    )

    print("\nChosen column:", trace.chosen + 1)
    print("Search depth:", trace.depth)
    print("Nodes searched:", trace.nodes)
    print("Time:", trace.time_s)
    print("TT statistics:", tt.stats())

    assert trace.chosen in board.legal_moves()
    assert trace.depth >= 1
