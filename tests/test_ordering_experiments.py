"""The Zobrist and killer-move experiments must not change the search result."""
from c4.board import Board
from eval import ordering_experiments as oe


def test_all_configurations_agree_on_root_scores():
    for moves in ("", "4453", "334455"):
        rows = [oe.run_configuration(moves, 4, c) for c in oe.CONFIGURATIONS]
        assert len({r["root_scores"] for r in rows}) == 1


def test_experiment_leaves_board_and_search_unpatched():
    from c4 import search as s
    oe.run_configuration("4453", 3, "zobrist+killers")
    assert Board.key is oe._ORIGINAL_KEY
    assert s._Searcher is oe._Searcher


def test_zobrist_gives_no_collisions_on_a_small_search():
    row = oe.run_configuration("4453", 5, "zobrist")
    assert row["collisions"] == 0 and row["distinct_keys"] > 100


def test_zobrist_and_exact_search_the_same_number_of_nodes():
    a = oe.run_configuration("4453", 5, "exact")
    b = oe.run_configuration("4453", 5, "zobrist")
    assert a["nodes"] == b["nodes"]