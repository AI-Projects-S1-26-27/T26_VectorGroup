"""Match harness: play two evaluators against each other.            OWNER: Mani

Proposal 4.5: 200 games between the learned and the hand-written evaluator at one
second per move, alternating who goes first, random openings; report win rates with
confidence intervals (target: the learned version wins at least 55%).

How the games are set up
  * N/2 random openings (2..8 random plies each, same range as the self-play data).
  * Every opening is played TWICE, once with A moving first and once with B moving
    first, so neither side gets a lucky opening and colours are balanced exactly.
  * Each side searches with c4.search at the same time limit per move (equal TIME, not
    equal depth), with its own transposition table and move ordering if they exist.
  * Score for A: win = 1, draw = 0.5, loss = 0.

Usage (repo root):
  python -m eval.match --a network --a-model models/nn_latest.pt --b heuristic \
         --games 200 --time-limit 1.0 --workers 3 --out results/match/network_vs_heuristic
  python -m eval.match --a heuristic --b heuristic --games 10 --depth 3   # quick test

Use --workers <= (CPU cores - 1): searching is time-limited, so a busy machine
makes every player weaker and the comparison unfair.
Writes <out>.csv (one row per game) and <out>.json (summary).
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
from c4.search import search
from eval.stats import bootstrap_mean_ci, wilson

TARGET = 0.55
_players: dict = {}


# ------------------------------------------------------------------ players
def _optional(module_name: str, attr: str):
    import importlib
    try:
        return getattr(importlib.import_module(module_name), attr)
    except ModuleNotFoundError as err:
        if err.name == module_name:
            return None
        raise


def make_evaluator(name: str, model=None):
    """'heuristic' | 'network' (needs model path) | 'module.path:ClassName'."""
    from c4.selfplay.generate import make_evaluator as _make
    return _make(name, model)


class Player:
    """One side of the match: an evaluator plus its own table and move ordering."""

    def __init__(self, evaluator_name, model=None, use_tt=True, use_ordering=True):
        self.evaluator = make_evaluator(evaluator_name, model)
        tt_cls = _optional("c4.tt", "TranspositionTable") if use_tt else None
        self.tt = tt_cls() if tt_cls else None
        self.order_fn = _optional("c4.ordering", "move_ordering") if use_ordering else None

    def new_game(self):
        if self.tt is not None:
            self.tt.clear()
        if hasattr(self.evaluator, "clear_cache"):
            self.evaluator.clear_cache()

    def choose(self, board: Board, time_limit, depth) -> int:
        trace = search(board, self.evaluator, time_limit=time_limit,
                       max_depth=depth, tt=self.tt, order_fn=self.order_fn)
        return trace.chosen


# -------------------------------------------------------------------- games
def random_opening(rng: random.Random, min_plies=2, max_plies=8) -> str:
    """A random legal opening, as a 1-indexed move string; never a finished game."""
    while True:
        board, moves = Board.empty(), ""
        for _ in range(rng.randint(min_plies, max_plies)):
            col = rng.choice(board.legal_moves())
            board, moves = board.play(col), moves + str(col + 1)
            if board.is_over():
                break
        if not board.is_over():
            return moves


def make_openings(n_openings: int, seed: int, min_plies=2, max_plies=8) -> list[str]:
    rng = random.Random(seed)
    out: list[str] = []
    while len(out) < n_openings:       # distinct openings where possible
        o = random_opening(rng, min_plies, max_plies)
        if o not in out or len(out) >= 500:
            out.append(o)
    return out


def play_game(opening: str, first: Player, second: Player, time_limit, depth):
    """Play one game. Returns (winner, moves) with winner 'first' / 'second' / 'draw'."""
    first.new_game()
    second.new_game()
    board = Board.from_moves(opening)
    # The opening is a set of random plies; whoever is due to move next is determined
    # by the parity of the opening, so colours are fixed by who is `first` at ply 0.
    players = (first, second)
    played = opening
    while not board.is_over():
        mover = players[board.num_moves & 1]
        col = mover.choose(board, time_limit, depth)
        board = board.play(col)
        played += str(col + 1)
    if board.is_draw():
        return "draw", played
    return ("first" if (board.num_moves - 1) & 1 == 0 else "second"), played


def _init_worker(cfg):
    _players["a"] = Player(cfg["a"], cfg["a_model"])
    _players["b"] = Player(cfg["b"], cfg["b_model"])
    _players["cfg"] = cfg


def _play_job(job):
    idx, opening, a_first = job
    a, b, cfg = _players["a"], _players["b"], _players["cfg"]
    t0 = time.perf_counter()
    if a_first:
        who, moves = play_game(opening, a, b, cfg["time_limit"], cfg["depth"])
        result = {"first": "A", "second": "B", "draw": "draw"}[who]
    else:
        who, moves = play_game(opening, b, a, cfg["time_limit"], cfg["depth"])
        result = {"first": "B", "second": "A", "draw": "draw"}[who]
    return dict(game=idx, opening=opening, a_first=int(a_first), winner=result,
                moves=moves, plies=len(moves), seconds=round(time.perf_counter() - t0, 2))


def summarise(rows: list[dict], target: float = TARGET) -> dict:
    """Wins/draws/losses of A, score with CIs. `rows` need opening, winner."""
    a_wins = sum(r["winner"] == "A" for r in rows)
    b_wins = sum(r["winner"] == "B" for r in rows)
    draws = len(rows) - a_wins - b_wins
    n = len(rows)
    score = (a_wins + 0.5 * draws) / n if n else float("nan")
    lo, hi = wilson(a_wins + 0.5 * draws, n)
    # paired bootstrap: the unit is the opening (its two games), not the game
    per_opening: dict[str, list[float]] = {}
    for r in rows:
        per_opening.setdefault(r["opening"], []).append(
            1.0 if r["winner"] == "A" else 0.5 if r["winner"] == "draw" else 0.0)
    pairs = [sum(v) / len(v) for v in per_opening.values()]
    blo, bhi = bootstrap_mean_ci(pairs)
    decisive = a_wins + b_wins
    dlo, dhi = wilson(a_wins, decisive)
    return dict(games=n, a_wins=a_wins, b_wins=b_wins, draws=draws,
                a_score=score, a_score_wilson95=[lo, hi], a_score_bootstrap95=[blo, bhi],
                a_win_rate_excluding_draws=(a_wins / decisive if decisive else float("nan")),
                a_win_rate_excluding_draws_wilson95=[dlo, dhi],
                target=target, target_met=bool(score >= target),
                target_clearly_met=bool(lo >= target))


def run(cfg: dict, quiet=False) -> dict:
    openings = make_openings(cfg["games"] // 2, cfg["seed"])
    jobs = []
    for i, o in enumerate(openings):
        jobs.append((2 * i, o, True))
        jobs.append((2 * i + 1, o, False))
    t0 = time.perf_counter()
    rows = []
    if cfg["workers"] <= 1:
        _init_worker(cfg)
        it = map(_play_job, jobs)
        pool = None
    else:
        pool = mp.get_context("spawn").Pool(cfg["workers"], _init_worker, (cfg,))
        it = pool.imap_unordered(_play_job, jobs)
    try:
        for r in it:
            rows.append(r)
            if not quiet:
                s = summarise(rows)
                print(f"[{len(rows)}/{len(jobs)}] A {s['a_wins']}  draw {s['draws']}  "
                      f"B {s['b_wins']}  A score {s['a_score']:.3f}", flush=True)
    finally:
        if pool is not None:
            pool.close()
            pool.join()
    rows.sort(key=lambda r: r["game"])
    summary = summarise(rows)
    summary.update(config={k: v for k, v in cfg.items()},
                   minutes=round((time.perf_counter() - t0) / 60, 2))
    return {"rows": rows, "summary": summary}


def save(result: dict, out: str) -> None:
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = result["rows"]
    with open(out_path.with_suffix(".csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    out_path.with_suffix(".json").write_text(json.dumps(result["summary"], indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--a", default="network", help="evaluator A (the one being tested)")
    p.add_argument("--a-model", default=None, help="weights file for A if it is a network")
    p.add_argument("--b", default="heuristic", help="evaluator B (the baseline)")
    p.add_argument("--b-model", default=None)
    p.add_argument("--games", type=int, default=200, help="even number; each opening is played twice")
    p.add_argument("--time-limit", type=float, default=1.0, help="seconds per move (equal time)")
    p.add_argument("--depth", type=int, default=42, help="max depth; lower it only for quick tests")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default="results/match/network_vs_heuristic")
    args = p.parse_args(argv)
    if args.games < 2 or args.games % 2:
        p.error("--games must be an even number >= 2")
    if args.time_limit <= 0:
        p.error("--time-limit must be positive")
    cfg = dict(a=args.a, a_model=args.a_model, b=args.b, b_model=args.b_model,
               games=args.games, time_limit=args.time_limit, depth=args.depth,
               workers=args.workers, seed=args.seed)
    result = run(cfg)
    save(result, args.out)
    s = result["summary"]
    print(json.dumps({k: s[k] for k in ("games", "a_wins", "draws", "b_wins", "a_score",
                                        "a_score_wilson95", "a_score_bootstrap95",
                                        "target_met", "target_clearly_met", "minutes")}, indent=2))


if __name__ == "__main__":
    main()
