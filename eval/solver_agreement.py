"""How often does the evaluator pick the right side as winning?     OWNER: Mani

Proposal 4.5: check how often the network's prediction of who is winning agrees with
the perfect solver on 2,000 unseen positions (target 80%).

  1. Sample positions: a few random opening plies, then a mix of random moves and
     shallow-search moves, stopped at a random ply in [--min-ply, --max-ply].
     Positions that occur in the training data (--exclude-data) are removed, mirror
     images included, so every position is truly unseen.
  2. Label each with the perfect solver (eval/solver.py): +1 mover wins, 0 draw, -1 loses.
  3. Ask each evaluator (network and the hand-written one) and compare.

Two numbers per evaluator
  * decisive_accuracy: among positions the solver says are won or lost, how often the
    sign of the evaluator's score is right. THIS is the proposal's 80% target.
  * three_class_accuracy: draws count too; |score| <= --draw-band is read as "draw".

Usage (repo root):
  python -m eval.solver_agreement --positions 2000 --model models/nn_latest.pt \
         --exclude-data data/selfplay/round_1 --workers 3
  python -m eval.solver_agreement --positions 50 --evaluators heuristic      # quick test
Writes results/solver_agreement/agreement.csv and .json.

Positions with few stones are slow for the built-in solver (min-ply 14 takes about
half a second each); build Pons's solver and set C4_SOLVER_BIN to go lower.
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import random
import time
from pathlib import Path

from c4.board import Board
from eval.solver import outcome, solve
from eval.stats import wilson


# ---------------------------------------------------------------- sampling
def sample_positions(n: int, seed: int = 0, min_ply: int = 14, max_ply: int = 30,
                     exclude_keys=frozenset(), p_random: float = 0.3) -> list[str]:
    """n distinct unfinished positions as 1-indexed move strings."""
    from c4.eval_heuristic import HeuristicEvaluator
    from c4.search import search
    if not 1 <= min_ply <= max_ply <= 40:
        raise ValueError("need 1 <= min_ply <= max_ply <= 40")
    rng = random.Random(seed)
    ev = HeuristicEvaluator()
    seen, out = set(), []
    attempts = 0
    while len(out) < n:
        attempts += 1
        if attempts > 200 * n + 1000:
            raise RuntimeError("could not sample enough distinct unseen positions")
        target = rng.randint(min_ply, max_ply)
        board, moves = Board.empty(), ""
        while board.num_moves < target and not board.is_over():
            if board.num_moves < 4 or rng.random() < p_random:
                col = rng.choice(board.legal_moves())
            else:
                col = search(board, ev, time_limit=5.0, max_depth=2).chosen
            board, moves = board.play(col), moves + str(col + 1)
        if board.is_over():
            continue
        keys = {board.key(), board.mirrored().key()}
        if keys & seen or keys & exclude_keys:
            continue
        seen |= keys
        out.append(moves)
    return out


def training_keys(round_dirs) -> set[int]:
    """Keys (and mirror keys) of every position in the training data."""
    import numpy as np
    from c4.selfplay.dataset import load_positions, mirror_bits, position_keys
    data = load_positions(round_dirs)
    keys = set(position_keys(data.position, data.mask).tolist())
    keys |= set(position_keys(mirror_bits(data.position), mirror_bits(data.mask)).tolist())
    return keys


# ---------------------------------------------------------------- labelling
def _label(moves: str) -> tuple[int, int]:
    board = Board.from_moves(moves)
    s = solve(board)                      # exact score; outcome is its sign
    return s, (s > 0) - (s < 0)


def label_positions(positions: list[str], workers: int = 1) -> list[tuple[int, int]]:
    if workers <= 1:
        return [_label(m) for m in positions]
    with mp.get_context("spawn").Pool(workers) as pool:
        return pool.map(_label, positions, chunksize=4)


# ---------------------------------------------------------------- scoring
def sign3(score: float, band: float) -> int:
    return 0 if abs(score) <= band else (1 if score > 0 else -1)


def evaluate_agreement(rows: list[dict], names: list[str], draw_band: float) -> dict:
    """rows: dicts with solver_outcome and a '<name>_score' column per evaluator."""
    out = {}
    decisive = [r for r in rows if r["solver_outcome"] != 0]
    for name in names:
        ok = sum(sign3(r[f"{name}_score"], 0) == r["solver_outcome"] for r in decisive)
        ok3 = sum(sign3(r[f"{name}_score"], draw_band) == r["solver_outcome"] for r in rows)
        lo, hi = wilson(ok, len(decisive))
        lo3, hi3 = wilson(ok3, len(rows))
        out[name] = dict(
            decisive_positions=len(decisive), decisive_correct=ok,
            decisive_accuracy=ok / len(decisive) if decisive else float("nan"),
            decisive_accuracy_wilson95=[lo, hi],
            three_class_accuracy=ok3 / len(rows) if rows else float("nan"),
            three_class_accuracy_wilson95=[lo3, hi3])
    return out


def by_ply_bucket(rows: list[dict], names: list[str], width: int = 6) -> dict:
    out: dict[str, dict] = {}
    for r in rows:
        if r["solver_outcome"] == 0:
            continue
        b = (r["ply"] // width) * width
        key = f"{b}-{b + width - 1}"
        d = out.setdefault(key, {"n": 0, **{n: 0 for n in names}})
        d["n"] += 1
        for n in names:
            d[n] += sign3(r[f"{n}_score"], 0) == r["solver_outcome"]
    for d in out.values():
        for n in names:
            d[n] = d[n] / d["n"]
    return dict(sorted(out.items(), key=lambda kv: int(kv[0].split("-")[0])))


def run(n, names, model, seed, min_ply, max_ply, exclude_data, workers, draw_band, quiet=False):
    exclude = training_keys(exclude_data) if exclude_data else frozenset()
    t0 = time.perf_counter()
    positions = sample_positions(n, seed, min_ply, max_ply, exclude)
    if not quiet:
        print(f"sampled {len(positions)} positions, solving...", flush=True)
    labels = label_positions(positions, workers)
    evaluators = {name: _evaluator(name, model) for name in names}
    rows = []
    for moves, (s, o) in zip(positions, labels):
        board = Board.from_moves(moves)
        row = dict(moves=moves, ply=board.num_moves, solver_score=s, solver_outcome=o)
        for name, ev in evaluators.items():
            row[f"{name}_score"] = ev.evaluate(board)
        rows.append(row)
    summary = dict(positions=len(rows), seed=seed, min_ply=min_ply, max_ply=max_ply,
                   excluded_training_positions=len(exclude), draw_band=draw_band,
                   solver_outcome_counts={k: sum(r["solver_outcome"] == k for r in rows)
                                          for k in (1, 0, -1)},
                   target=0.80, evaluators=evaluate_agreement(rows, names, draw_band),
                   by_ply=by_ply_bucket(rows, names),
                   minutes=round((time.perf_counter() - t0) / 60, 2))
    return rows, summary


def _evaluator(name: str, model):
    from eval.match import make_evaluator
    return make_evaluator(name, model if name == "network" else None)


def save(rows, summary, out_dir: str):
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "agreement.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (d / "agreement.json").write_text(json.dumps(summary, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--positions", type=int, default=2000)
    p.add_argument("--evaluators", nargs="+", default=["network", "heuristic"])
    p.add_argument("--model", default=None, help="network weights (default models/nn_latest.pt)")
    p.add_argument("--exclude-data", nargs="*", default=None,
                   help="round folders (e.g. data/selfplay/round_1) whose positions to avoid")
    p.add_argument("--min-ply", type=int, default=14)
    p.add_argument("--max-ply", type=int, default=30)
    p.add_argument("--seed", type=int, default=12345, help="use a seed no one trained with")
    p.add_argument("--draw-band", type=float, default=100,
                   help="|score| <= band counts as 'draw' for the three-class accuracy")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--out", default="results/solver_agreement")
    a = p.parse_args(argv)
    rows, summary = run(a.positions, a.evaluators, a.model, a.seed, a.min_ply, a.max_ply,
                        a.exclude_data, a.workers, a.draw_band)
    save(rows, summary, a.out)
    print(json.dumps({"positions": summary["positions"],
                      "solver_outcome_counts": summary["solver_outcome_counts"],
                      **{n: {k: v for k, v in e.items() if k.startswith(("decisive_acc", "three"))}
                         for n, e in summary["evaluators"].items()}}, indent=2))


if __name__ == "__main__":
    main()
