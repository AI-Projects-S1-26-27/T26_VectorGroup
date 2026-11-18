"""Experiment: Zobrist key and killer moves, at fixed depth (not used by the agent).

    python -m eval.ordering_experiments --depth 8 --count 100 --workers 3 --out results/ordering_experiments.csv --summary results/ordering_experiments_summary.json

The proposal named Zobrist hashing and killer moves. The agent uses the exact board key
and no killer moves. This script measures both ideas WITHOUT changing any file in c4/:
it swaps them in for one run each (by temporarily replacing `Board.key` and the search's
`_Searcher` class) and compares four configurations, all with the transposition table and
the normal move ordering, on the same seeded positions as eval/node_counts.py:

    exact            exact key (position + mask), no killers     <- what the agent uses
    zobrist          64-bit Zobrist-style key, no killers
    exact+killers    exact key, two killer moves per ply
    zobrist+killers  both ideas together, as the proposal described

Node counts at a fixed depth are deterministic, so they are the main measure; times are
secondary. Every configuration must return the same root scores, which is checked.
"""
import argparse
import csv
import json
import random
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import c4.search as search_module
from c4.board import Board, SIZE
from c4.eval_heuristic import HeuristicEvaluator
from c4.ordering import move_ordering
from c4.search import search, _Searcher, _to_tt, _from_tt, _TimeUp, INF
from c4.trace import WIN_SCORE
from c4.tt import TranspositionTable
from eval.node_counts import fixed_positions

CONFIGURATIONS = ("exact", "zobrist", "exact+killers", "zobrist+killers")

# ---------------------------------------------------------------- Zobrist-style key
_NB = 7                                   # 49 bits = 7 bytes
_rng = random.Random(20261118)


def _byte_tables():
    bit_keys = [_rng.getrandbits(64) for _ in range(_NB * 8)]
    tables = [[0] * 256 for _ in range(_NB)]
    for b in range(_NB):
        for v in range(1, 256):
            low = (v & -v).bit_length() - 1
            tables[b][v] = tables[b][v & (v - 1)] ^ bit_keys[8 * b + low]
    return tables


_Z_POSITION, _Z_MASK = _byte_tables(), _byte_tables()
_ORIGINAL_KEY = Board.key
_seen = {}                                # zobrist key -> exact key, to count collisions
_collisions = 0


def _zobrist_key(self):
    """Hash of (stones of the side to move, occupied cells): XOR of random 64-bit numbers,
    one per set bit, as in Zobrist's method. Collisions are counted, not handled."""
    global _collisions
    p, m, h = self.position, self.mask, 0
    for b in range(_NB):
        s = 8 * b
        h ^= _Z_POSITION[b][(p >> s) & 255] ^ _Z_MASK[b][(m >> s) & 255]
    exact = p + m
    old = _seen.setdefault(h, exact)
    if old != exact:
        _collisions += 1
    return h


# ---------------------------------------------------------------- killer moves
class _KillerSearcher(_Searcher):
    """The agent's negamax with two killer moves per ply. A killer is a move that caused
    a beta cut-off at the same ply in a sibling node; it is tried early here. The order is:
    table move, blocks of an immediate opponent win, killers, then the normal order."""

    def __init__(self, evaluator, tt, order_fn):
        super().__init__(evaluator, tt, order_fn)
        self.killers = [[None, None] for _ in range(SIZE + 3)]

    def _order(self, board, moves, tt_move, ply):
        if self.order_fn is not None:
            base = list(self.order_fn(board, moves, tt_move))
        else:
            base = list(moves)
            if tt_move is not None and tt_move in base:
                base.remove(tt_move)
                base.insert(0, tt_move)
        killers = [k for k in self.killers[ply] if k is not None and k in moves and k != tt_move]
        if not killers:
            return base
        opponent = Board(board.mask ^ board.position, board.mask)
        blocks = set(opponent.winning_moves())
        head = [m for m in base if m == tt_move or m in blocks]
        rest = [m for m in base if m not in head]
        picked = [k for k in killers if k in rest]
        return head + picked + [m for m in rest if m not in picked]

    def negamax(self, board, depth, alpha, beta, ply):
        # Same logic as c4.search._Searcher.negamax; only the ordering and the killer
        # update differ.
        self.nodes += 1
        if self.nodes & 63 == 0 and time.perf_counter() > self.deadline:
            raise _TimeUp
        self.pv[ply] = []

        from c4.board import CENTER_FIRST
        from c4.search import EXACT, LOWER, UPPER
        moves = [c for c in CENTER_FIRST if board.can_play(c)]
        if not moves:
            return 0
        for c in moves:
            if board.wins_by_playing(c):
                self.pv[ply] = [c]
                return WIN_SCORE - (ply + 1)
        if depth == 0:
            return self.evaluator.evaluate(board)

        alpha_orig = alpha
        key = board.key()
        tt_move = None
        if self.tt is not None:
            entry = self.tt.probe(key)
            if entry is not None:
                e_depth, e_value, e_flag, e_move = entry
                tt_move = e_move
                if e_depth >= depth and ply > 1:
                    value = _from_tt(e_value, ply)
                    if e_flag == EXACT:
                        return value
                    if e_flag == LOWER:
                        alpha = max(alpha, value)
                    else:
                        beta = min(beta, value)
                    if alpha >= beta:
                        return value

        moves = self._order(board, moves, tt_move, ply)

        best = -INF
        best_move = None
        for c in moves:
            score = -self.negamax(board.play_unchecked(c), depth - 1, -beta, -alpha, ply + 1)
            if score > best:
                best = score
                best_move = c
                if score > alpha:
                    alpha = score
                    self.pv[ply] = [c] + self.pv[ply + 1]
                    if alpha >= beta:
                        slot = self.killers[ply]
                        if slot[0] != c:
                            slot[1] = slot[0]
                            slot[0] = c
                        break

        if self.tt is not None:
            if best <= alpha_orig:
                flag = UPPER
            elif best >= beta:
                flag = LOWER
            else:
                flag = EXACT
            self.tt.store(key, depth, _to_tt(best, ply), flag, best_move)
        return best


# ---------------------------------------------------------------- one run
def run_configuration(moves, depth, configuration, time_limit=3600.0):
    """Search one position with one configuration and return a CSV-ready row."""
    global _collisions
    zobrist = configuration.startswith("zobrist")
    killers = configuration.endswith("killers")
    board = Board.from_moves(moves)
    _seen.clear()
    _collisions = 0
    if zobrist:
        Board.key = _zobrist_key
    if killers:
        search_module._Searcher = _KillerSearcher
    try:
        tt = TranspositionTable()
        trace = search(board, HeuristicEvaluator(), time_limit=time_limit,
                       max_depth=depth, tt=tt, order_fn=move_ordering)
    finally:
        Board.key = _ORIGINAL_KEY
        search_module._Searcher = _Searcher
    return dict(position=moves, configuration=configuration, requested_depth=depth,
                completed_depth=trace.depth, nodes=trace.nodes, time_s=round(trace.time_s, 4),
                chosen=trace.chosen, score=trace.score,
                root_scores=json.dumps({c: m.score for c, m in trace.moves.items()}),
                tt_hits=tt.stats()["hits"], distinct_keys=len(_seen) if zobrist else "",
                collisions=_collisions if zobrist else "")


def _job(args):
    return [run_configuration(args[0], args[1], c) for c in CONFIGURATIONS]


def run_all(positions, depth, workers=1, progress=False):
    jobs = [(p, depth) for p in positions]
    rows = []
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, result in enumerate(pool.map(_job, jobs), 1):
                rows.extend(result)
                if progress:
                    print(f"Completed {i}/{len(jobs)} positions", file=sys.stderr, flush=True)
    else:
        for i, job in enumerate(jobs, 1):
            rows.extend(_job(job))
            if progress:
                print(f"Completed {i}/{len(jobs)} positions", file=sys.stderr, flush=True)
    return rows


# ---------------------------------------------------------------- summary
def key_speed(samples=20000, seed=1):
    """Seconds per key() call for the exact key and the Zobrist-style key."""
    rng = random.Random(seed)
    boards = []
    while len(boards) < 200:
        b = Board.empty()
        for _ in range(rng.randint(5, 30)):
            if b.is_over():
                break
            b = b.play(rng.choice(b.legal_moves()))
        boards.append(b)
    out = {}
    for name, fn in (("exact", _ORIGINAL_KEY), ("zobrist", _zobrist_key)):
        t = time.perf_counter()
        for i in range(samples):
            fn(boards[i % 200])
        out[name + "_us_per_key"] = round((time.perf_counter() - t) / samples * 1e6, 3)
    _seen.clear()
    return out


def summarize(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r["position"], {})[r["configuration"]] = r
    complete, score_mismatch = [], []
    for position, g in groups.items():
        if all(int(r["completed_depth"]) == int(r["requested_depth"]) for r in g.values()):
            complete.append(g)
            if len({r["root_scores"] for r in g.values()}) != 1:
                score_mismatch.append(position)
    totals = {c: sum(int(g[c]["nodes"]) for g in complete) for c in CONFIGURATIONS}
    seconds = {c: round(sum(float(g[c]["time_s"]) for g in complete), 2) for c in CONFIGURATIONS}
    base = totals["exact"]

    def ratio(a, b):
        return [int(g[a]["nodes"]) / int(g[b]["nodes"]) for g in complete]

    summary = dict(
        positions=len(groups), full_depth_positions=len(complete),
        requested_depth=sorted({int(r["requested_depth"]) for r in rows}),
        total_nodes=totals, total_time_s=seconds,
        nodes_vs_exact={c: round(totals[c] / base, 4) for c in CONFIGURATIONS} if base else None,
        reduction_zobrist_vs_exact=round(base / totals["zobrist"], 4) if totals["zobrist"] else None,
        reduction_killers_vs_exact=round(base / totals["exact+killers"], 4) if totals["exact+killers"] else None,
        reduction_both_vs_exact=round(base / totals["zobrist+killers"], 4) if totals["zobrist+killers"] else None,
        median_reduction_killers=round(statistics.median(ratio("exact", "exact+killers")), 4) if complete else None,
        positions_where_killers_fewer=sum(1 for g in complete if int(g["exact+killers"]["nodes"]) < int(g["exact"]["nodes"])),
        positions_where_killers_more=sum(1 for g in complete if int(g["exact+killers"]["nodes"]) > int(g["exact"]["nodes"])),
        score_mismatch_positions=score_mismatch,
        zobrist_collisions=sum(int(r["collisions"]) for r in rows if r["collisions"] != ""),
        zobrist_distinct_keys=sum(int(r["distinct_keys"]) for r in rows if r["distinct_keys"] != ""),
    )
    summary.update(key_speed())
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--depth", type=int, default=8)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=26)
    parser.add_argument("--positions", nargs="+", default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args(argv)
    positions = args.positions if args.positions is not None else fixed_positions(args.count, args.seed)
    rows = run_all(positions, args.depth, args.workers, args.progress)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    summary = summarize(rows)
    summary.update(seed=args.seed if args.positions is None else None, workers=args.workers)
    text = json.dumps(summary, indent=2)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()