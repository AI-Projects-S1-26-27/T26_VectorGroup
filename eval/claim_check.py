"""Brute-force check of every tactical claim the rules make.   OWNER: Naman

Plays random positions, runs the rules on every root move, and re-checks each
win / block / threat / fork / setup / trap claim by actually trying the moves
on the board (Board.wins_by_playing), without using c4/explain/facts.py.
Target from the proposal: at least 98% of claims correct on 500 positions.

    python -m eval.claim_check            # 500 positions
    python -m eval.claim_check -n 50 --seed 1
"""
from __future__ import annotations

import argparse
import random
from collections import Counter

from c4.board import Board, H1, has_alignment
from c4.explain.rules import detect_facts
from c4.search import search

CHECKED = ("win", "block", "threat", "fork", "setup", "trap")


class _Zero:
    """Facts do not depend on the evaluator, so use the cheapest one."""
    name = "zero"

    def evaluate(self, board):
        return 0


def _opponent_view(b: Board) -> Board:
    """Same stones, but the OTHER side is to move."""
    return Board(b.position ^ b.mask, b.mask)


def _completes_four(stones: int, mask: int, cell) -> bool:
    r, c = cell
    bit = 1 << (c * H1 + r)
    return not (mask & bit) and has_alignment(stones | bit)


def check_claim(board: Board, col: int, fact) -> bool:
    """True if `fact` (about playing `col` on `board`) is really true."""
    child = board.play(col)
    agent = child.position ^ child.mask           # agent's stones after the move
    if fact.kind == "win":
        return board.wins_by_playing(col)
    if fact.kind == "block":
        return _opponent_view(board).wins_by_playing(col)
    if fact.kind == "trap":
        return child.can_play(col) and child.wins_by_playing(col)
    if fact.kind == "fork":
        return len(_opponent_view(child).winning_moves()) >= 2
    if fact.kind in ("threat", "setup"):
        r, c = fact.cells[0]
        ok = _completes_four(agent, child.mask, (r, c))
        playable = child.height(c) == r
        return ok and playable == (fact.detail == "playable")
    raise ValueError(fact.kind)


def random_position(rng: random.Random) -> Board:
    """A random legal, unfinished position after 4-30 moves."""
    while True:
        b = Board.empty()
        for _ in range(rng.randint(4, 30)):
            b = b.play(rng.choice(b.legal_moves()))
            if b.is_over():
                break
        if not b.is_over():
            return b


def run(n: int = 500, seed: int = 0):
    rng = random.Random(seed)
    total, correct = Counter(), Counter()
    wrong = []
    for _ in range(n):
        board = random_position(rng)
        trace = detect_facts(search(board, _Zero(), max_depth=1))
        for move in trace.moves.values():
            for fact in move.facts:
                if fact.kind not in CHECKED:
                    continue
                total[fact.kind] += 1
                if check_claim(board, move.col, fact):
                    correct[fact.kind] += 1
                else:
                    wrong.append((board.render(), move.col, fact))
    return total, correct, wrong


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    total, correct, wrong = run(args.n, args.seed)
    for kind in CHECKED:
        if total[kind]:
            print(f"{kind:8s} {correct[kind]:6d}/{total[kind]:<6d} "
                  f"{100 * correct[kind] / total[kind]:6.2f}%")
    t, c = sum(total.values()), sum(correct.values())
    print(f"{'all':8s} {c:6d}/{t:<6d} {100 * c / max(t, 1):6.2f}%")
    for render, col, fact in wrong[:5]:
        print(f"\nWRONG: {fact} for column {col + 1}\n{render}")


if __name__ == "__main__":
    main()
