"""Measure search depth, nodes and speed at a fixed time limit.

Compares plain alpha-beta, alpha-beta with transposition table and move
ordering, and the network evaluator, on three positions.

Run from the repo root:  python -m eval.measure_search
"""
import os

from c4.board import Board
from c4.search import search
from c4.eval_heuristic import HeuristicEvaluator
from c4.ordering import move_ordering
from c4.tt import TranspositionTable
from c4.nn.evaluator import NNEvaluator

TIME_LIMIT = 1.0
MODEL_PATH = os.environ.get("C4_MODEL", "models/nn_latest.pt")

# empty board, early middlegame, later middlegame (columns 0-6)
POSITIONS = {
    "empty":  [],
    "early":  [3, 3, 2, 4, 3, 2],
    "middle": [3, 3, 2, 4, 3, 2, 4, 4, 1, 5, 2, 2, 5, 1],
}


def row(name, mode, t):
    print(f"{name:8} {mode:14} {t.depth:5d} {t.nodes:10d} "
          f"{t.time_s:7.2f} {t.nodes / t.time_s:10.0f}")


def main():
    heuristic = HeuristicEvaluator()
    network = NNEvaluator(MODEL_PATH)

    print(f"time limit {TIME_LIMIT}s per search")
    print(f"{'position':8} {'mode':14} {'depth':>5} {'nodes':>10} "
          f"{'time_s':>7} {'nodes/s':>10}")

    print("--- heuristic ---")
    for name, moves in POSITIONS.items():
        b = Board.from_moves(moves)
        row(name, "plain", search(b, heuristic, time_limit=TIME_LIMIT))
        row(name, "table+ordering",
            search(b, heuristic, time_limit=TIME_LIMIT,
                   tt=TranspositionTable(), order_fn=move_ordering))

    print("--- network ---")
    for name, moves in POSITIONS.items():
        b = Board.from_moves(moves)
        row(name, "network",
            search(b, network, time_limit=TIME_LIMIT,
                   tt=TranspositionTable(), order_fn=move_ordering))


if __name__ == "__main__":
    main()