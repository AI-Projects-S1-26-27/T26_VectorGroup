"""Compare search nodes at equal depth: python -m eval.node_counts --depth 4.

Each position/configuration gets a fresh table. Timed-out or early-decided runs
report the actual completed depth, so their node totals can be interpreted.
"""
import argparse
import csv
import sys

from c4.board import Board
from c4.eval_heuristic import HeuristicEvaluator
from c4.ordering import move_ordering
from c4.search import search
from c4.tt import TranspositionTable

DEFAULT_POSITIONS = ("", "4453", "334455")


def compare_node_counts(positions=DEFAULT_POSITIONS, depth=4, time_limit=60.0):
    """Return CSV-ready rows for baseline, ordering, table, and both hooks."""
    if depth < 1 or time_limit <= 0:
        raise ValueError("depth and time_limit must be positive")
    rows = []
    for moves in positions:
        board = Board.from_moves(moves)
        if board.is_over():
            raise ValueError(f"finished benchmark position: {moves!r}")
        for label, use_tt, use_order in (
            ("baseline", False, False), ("ordering", False, True),
            ("tt", True, False), ("tt+ordering", True, True),
        ):
            tt = TranspositionTable() if use_tt else None
            trace = search(board, HeuristicEvaluator(), time_limit=time_limit,
                           max_depth=depth, tt=tt,
                           order_fn=move_ordering if use_order else None)
            rows.append(dict(position=moves, configuration=label,
                             requested_depth=depth, completed_depth=trace.depth,
                             nodes=trace.nodes, time_s=trace.time_s,
                             chosen=trace.chosen, score=trace.score,
                             tt_hits=tt.stats()["hits"] if tt is not None else 0))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--positions", nargs="+", default=DEFAULT_POSITIONS,
                        help="1-indexed move strings; use an empty string for the opening")
    args = parser.parse_args(argv)
    if args.depth < 1 or args.time_limit <= 0:
        parser.error("depth and time-limit must be positive")
    rows = compare_node_counts(args.positions, args.depth, args.time_limit)
    writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)


if __name__ == "__main__":
    main()
