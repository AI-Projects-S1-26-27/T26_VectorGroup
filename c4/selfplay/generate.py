"""Self-play data generation.                              OWNER: Veer

The agent plays Connect-4 against itself and every position it sees is saved
with the final result of its game. This is the training data for the network
(c4/nn, Sriyanth).

How one game is played
  1. The first few moves (2 to 8 by default, chosen at random per game) are
     random legal moves, so games start from many different openings.
  2. After that every move is chosen by the real search (c4/search.py) with the
     chosen evaluator. If several moves share the best score, one of them is
     picked at random, which adds variety without weakening play.
     Optionally (--epsilon) a small share of later moves are random too.
  3. When the game ends, every position in it is labelled from the point of
     view of the player TO MOVE there:  +1 = that player went on to win,
     -1 = that player lost,  0 = draw.  (Same viewpoint as scores in trace.py.)
     Finished positions are not stored: the evaluator is never asked about them.

Rounds (proposal section 4.2)
  round 1: games played with the hand-written evaluator (Rujuta)
  round 2+: games played with the previous network (Sriyanth), --evaluator network

Output, one folder per round:
  data/selfplay/round_1/meta.json          settings used + totals
  data/selfplay/round_1/shard_00000.npz    games 0..499
  data/selfplay/round_1/shard_00001.npz    games 500..999   ...
Each shard holds one row per position (see SHARD_FIELDS below). Load them with
c4/selfplay/dataset.py, not by hand.

Shards are written one at a time, so a long run can be stopped with Ctrl+C and
started again with the same command: finished shards are skipped. Every game has
its own seed, so with a fixed depth the same command always gives the same data.

Usage (from the repo root):
  python -m c4.selfplay.generate --games 200 --round 0                    # quick test
  python -m c4.selfplay.generate --games 50000 --round 1 --workers 6
  python -m c4.selfplay.generate --games 20000 --round 2 --evaluator network \\
         --model models/round1.pt --workers 6

Speed (measured with Rujuta's evaluator, table and ordering, one CPU core):
  depth 4: about 4 games/s   ->  50,000 games in about 35 min with 6 workers
  depth 6: about 0.7 games/s ->  50,000 games in about 3.5 h with 6 workers
"""
from __future__ import annotations

import argparse
import importlib
import json
import multiprocessing as mp
import os
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from c4.board import Board
from c4.search import search

# One row per stored position.
SHARD_FIELDS = {
    "position": np.uint64,  # Board.position  (stones of the player to move)
    "mask": np.uint64,      # Board.mask      (all stones)   -> Board(position, mask)
    "result": np.int8,      # +1 / 0 / -1 for the player to move (final game result)
    "game": np.int64,       # unique game id = round * GAME_ID_BASE + index in round
    "ply": np.int8,         # stones on the board (0 = empty board)
    "move": np.int8,        # column (0-6) that was played from this position
    "score": np.int32,      # search score of that move, NO_SCORE if it was random
    "random": np.bool_,     # True if the move played here was a random move
}
NO_SCORE = np.iinfo(np.int32).min
GAME_ID_BASE = 1_000_000          # so games from different rounds never share an id

EVALUATORS = {
    "heuristic": "c4.eval_heuristic:HeuristicEvaluator",   # Rujuta
    "network": "c4.nn.evaluator:NNEvaluator",              # Sriyanth
}


@dataclass
class SelfPlayConfig:
    games: int = 1000
    round: int = 1
    evaluator: str = "heuristic"     # "heuristic", "network", or "module.path:ClassName"
    model: Optional[str] = None      # weights file for the network evaluator
    depth: int = 4                   # search depth per move (plies)
    time_limit: Optional[float] = None   # seconds per move; None = no limit, use depth only
    min_random: int = 2              # random opening moves per game: min ...
    max_random: int = 8              # ... and max (inclusive)
    epsilon: float = 0.0             # chance of a random move after the opening
    use_tt: bool = True              # use Rujuta's transposition table if it exists
    use_ordering: bool = True        # use Rujuta's move ordering if it exists
    seed: int = 0
    games_per_shard: int = 500
    out_dir: str = "data/selfplay"
    workers: int = 1
    extra: dict = field(default_factory=dict)   # free-form notes stored in meta.json

    def round_dir(self) -> Path:
        return Path(self.out_dir) / f"round_{self.round}"

    def data_settings(self) -> dict:
        """Settings that change the data. A round folder must not mix two of these."""
        d = asdict(self)
        for k in ("games", "workers", "out_dir", "games_per_shard", "extra"):
            d.pop(k)
        return d


# ----------------------------------------------------------------- pluggables
def _load_attr(spec: str):
    module_name, _, attr = spec.partition(":")
    if not attr:
        raise ValueError(f"evaluator spec must look like 'package.module:ClassName', got {spec!r}")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as err:
        if err.name == module_name:
            raise RuntimeError(
                f"{module_name} is not on this branch yet. Pull main after its owner "
                f"has merged it (git checkout main && git pull, then merge main into "
                f"your branch).") from err
        raise
    return getattr(module, attr)


def make_evaluator(name: str, model: Optional[str] = None):
    """Build the evaluator used by the search.

    The network evaluator is built with NNEvaluator.load(model) if that method
    exists, otherwise NNEvaluator(model)."""
    cls = _load_attr(EVALUATORS.get(name, name))
    if name == "network":
        if not model:
            raise ValueError("--evaluator network needs --model <weights file>")
        loader = getattr(cls, "load", None)
        return loader(model) if callable(loader) else cls(model)
    return cls(model) if model else cls()


def _optional(module_name: str, attr: str):
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as err:
        if err.name == module_name:
            return None
        raise
    return getattr(module, attr, None)


def make_search_helpers(cfg: SelfPlayConfig):
    """Transposition table and move ordering (Rujuta). Missing ones are skipped,
    so self-play still runs (just slower) before her branch is merged."""
    tt = order_fn = None
    if cfg.use_tt:
        tt_cls = _optional("c4.tt", "TranspositionTable")
        tt = tt_cls() if tt_cls is not None else None
    if cfg.use_ordering:
        order_fn = _optional("c4.ordering", "move_ordering")
    return tt, order_fn


# ------------------------------------------------------------------ one game
def game_rng(cfg: SelfPlayConfig, index: int) -> random.Random:
    """Each game has its own seed, so games do not depend on worker order."""
    return random.Random(f"c4-selfplay/{cfg.seed}/{cfg.round}/{index}")


def play_game(cfg: SelfPlayConfig, index: int, evaluator, tt=None, order_fn=None) -> dict:
    """Play one self-play game and return its positions as a dict of lists
    (same keys as SHARD_FIELDS) plus 'winner': 0 = X, 1 = O, None = draw."""
    rng = game_rng(cfg, index)
    n_random = rng.randint(cfg.min_random, cfg.max_random)
    time_limit = cfg.time_limit if cfg.time_limit is not None else float("inf")
    if tt is not None and hasattr(tt, "clear"):
        tt.clear()                   # every game starts fresh: reproducible

    board = Board.empty()
    rows = {k: [] for k in SHARD_FIELDS}
    while not board.is_over():
        legal = board.legal_moves()
        is_random = board.num_moves < n_random or (cfg.epsilon > 0 and rng.random() < cfg.epsilon)
        if is_random:
            col, score = rng.choice(legal), int(NO_SCORE)
        else:
            trace = search(board, evaluator, time_limit=time_limit, max_depth=cfg.depth,
                           tt=tt, order_fn=order_fn)
            best = [c for c, m in trace.moves.items() if m.score == trace.score]
            col = trace.chosen if len(best) == 1 else rng.choice(sorted(best))
            score = trace.score
        rows["position"].append(board.position)
        rows["mask"].append(board.mask)
        rows["ply"].append(board.num_moves)
        rows["move"].append(col)
        rows["score"].append(score)
        rows["random"].append(is_random)
        board = board.play(col)

    if board.last_mover_won():
        winner = (board.num_moves - 1) & 1           # player who made the last move
        rows["result"] = [1 if (p & 1) == winner else -1 for p in rows["ply"]]
    else:
        winner = None
        rows["result"] = [0] * len(rows["ply"])
    rows["game"] = [cfg.round * GAME_ID_BASE + index] * len(rows["ply"])
    rows["winner"] = winner
    return rows


# ---------------------------------------------------------------- shards
def shard_path(cfg: SelfPlayConfig, shard: int) -> Path:
    return cfg.round_dir() / f"shard_{shard:05d}.npz"


def num_shards(cfg: SelfPlayConfig) -> int:
    return -(-cfg.games // cfg.games_per_shard)


def shard_games(cfg: SelfPlayConfig, shard: int) -> range:
    start = shard * cfg.games_per_shard
    return range(start, min(start + cfg.games_per_shard, cfg.games))


def write_shard(path: Path, games: list[dict]) -> None:
    arrays = {k: np.array([v for g in games for v in g[k]], dtype=dt)
              for k, dt in SHARD_FIELDS.items()}
    tmp = path.with_name(path.stem + ".tmp.npz")
    np.savez_compressed(tmp, **arrays)
    os.replace(tmp, path)             # a shard file is either complete or absent


def play_shard(cfg: SelfPlayConfig, shard: int, evaluator, tt=None, order_fn=None) -> dict:
    games = [play_game(cfg, i, evaluator, tt, order_fn) for i in shard_games(cfg, shard)]
    write_shard(shard_path(cfg, shard), games)
    winners = [g["winner"] for g in games]
    return {"shard": shard, "games": len(games),
            "positions": sum(len(g["ply"]) for g in games),
            "x_wins": winners.count(0), "o_wins": winners.count(1),
            "draws": winners.count(None)}


# ------------------------------------------------- worker processes (spawn-safe)
_WORKER: dict = {}


def _init_worker(cfg: SelfPlayConfig) -> None:
    try:
        import torch                  # one thread per process; the processes are the parallelism
        torch.set_num_threads(1)
    except ImportError:
        pass
    tt, order_fn = make_search_helpers(cfg)
    _WORKER.update(cfg=cfg, evaluator=make_evaluator(cfg.evaluator, cfg.model),
                   tt=tt, order_fn=order_fn)


def _worker_shard(shard: int) -> dict:
    w = _WORKER
    return play_shard(w["cfg"], shard, w["evaluator"], w["tt"], w["order_fn"])


# ------------------------------------------------------------------- driver
def _check_meta(cfg: SelfPlayConfig, force: bool) -> None:
    meta_path = cfg.round_dir() / "meta.json"
    if meta_path.exists() and not force:
        old = json.loads(meta_path.read_text())
        if old.get("settings") != cfg.data_settings():
            raise SystemExit(
                f"{cfg.round_dir()} already holds data made with different settings:\n"
                f"  old: {old.get('settings')}\n  new: {cfg.data_settings()}\n"
                f"Use a new --round, or --force to mix them anyway.")


def _write_meta(cfg: SelfPlayConfig, totals: Optional[dict] = None) -> None:
    meta = {"settings": cfg.data_settings(), "games_requested": cfg.games,
            "games_per_shard": cfg.games_per_shard, "fields": list(SHARD_FIELDS),
            "extra": cfg.extra}
    if totals is not None:
        meta["totals"] = totals
    (cfg.round_dir() / "meta.json").write_text(json.dumps(meta, indent=2))


def summarise_round(cfg: SelfPlayConfig) -> dict:
    """Totals over every finished shard in the round folder."""
    positions, x_results = 0, []
    for path in sorted(cfg.round_dir().glob("shard_?????.npz")):
        with np.load(path) as z:
            positions += len(z["ply"])
            # every game starts from the empty board (ply 0, X to move), so the
            # result stored there is the game's result for X
            x_results.extend(z["result"][z["ply"] == 0].tolist())
    return {"games": len(x_results), "positions": positions,
            "x_wins": x_results.count(1), "o_wins": x_results.count(-1),
            "draws": x_results.count(0)}


def run(cfg: SelfPlayConfig, force: bool = False, quiet: bool = False) -> dict:
    """Generate the whole round. Returns the totals written to meta.json."""
    def say(msg):
        if not quiet:
            print(msg, flush=True)

    cfg.round_dir().mkdir(parents=True, exist_ok=True)
    _check_meta(cfg, force)
    _write_meta(cfg)
    todo = [s for s in range(num_shards(cfg)) if not shard_path(cfg, s).exists()]
    done = num_shards(cfg) - len(todo)
    say(f"self-play round {cfg.round}: {cfg.games} games, evaluator={cfg.evaluator}, "
        f"depth={cfg.depth}, {len(todo)} shard(s) to play, {done} already done, "
        f"{cfg.workers} worker(s)")
    if not todo:
        totals = summarise_round(cfg)
        _write_meta(cfg, totals)
        return totals

    start = time.perf_counter()
    games_done = 0
    total_new = sum(len(shard_games(cfg, s)) for s in todo)

    def report(info):
        nonlocal games_done
        games_done += info["games"]
        rate = games_done / (time.perf_counter() - start)
        eta = (total_new - games_done) / rate if rate > 0 else 0
        say(f"  shard {info['shard']:5d}: {info['games']} games, {info['positions']} positions "
            f"(X {info['x_wins']} / O {info['o_wins']} / draw {info['draws']})  "
            f"[{games_done}/{total_new}, {rate:.2f} games/s, ETA {eta / 60:.1f} min]")

    if cfg.workers <= 1:
        _init_worker(cfg)
        for s in todo:
            report(_worker_shard(s))
    else:
        ctx = mp.get_context("spawn")     # same behaviour on Windows, Mac and Linux
        with ctx.Pool(cfg.workers, initializer=_init_worker, initargs=(cfg,)) as pool:
            for info in pool.imap_unordered(_worker_shard, todo):
                report(info)

    totals = summarise_round(cfg)
    _write_meta(cfg, totals)
    say(f"done in {(time.perf_counter() - start) / 60:.1f} min: {totals}")
    return totals


def parse_args(argv=None) -> tuple[SelfPlayConfig, bool]:
    d = SelfPlayConfig()
    p = argparse.ArgumentParser(description="Generate Connect-4 self-play training data.")
    p.add_argument("--games", type=int, default=d.games)
    p.add_argument("--round", type=int, default=d.round, help="round number (output folder)")
    p.add_argument("--evaluator", default=d.evaluator,
                   help="heuristic | network | package.module:ClassName")
    p.add_argument("--model", default=None, help="weights file for --evaluator network")
    p.add_argument("--depth", type=int, default=d.depth, help="search depth per move")
    p.add_argument("--time-limit", type=float, default=None,
                   help="seconds per move (optional; data is then not reproducible)")
    p.add_argument("--min-random", type=int, default=d.min_random)
    p.add_argument("--max-random", type=int, default=d.max_random)
    p.add_argument("--epsilon", type=float, default=d.epsilon)
    p.add_argument("--no-tt", action="store_true", help="do not use the transposition table")
    p.add_argument("--no-ordering", action="store_true", help="do not use move ordering")
    p.add_argument("--seed", type=int, default=d.seed)
    p.add_argument("--games-per-shard", type=int, default=d.games_per_shard)
    p.add_argument("--out", default=d.out_dir, help="parent folder for round_N folders")
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    p.add_argument("--force", action="store_true",
                   help="allow different settings in an existing round folder")
    a = p.parse_args(argv)
    if not 0 <= a.min_random <= a.max_random:
        p.error("need 0 <= --min-random <= --max-random")
    if a.depth < 1:
        p.error("--depth must be at least 1")
    cfg = SelfPlayConfig(games=a.games, round=a.round, evaluator=a.evaluator, model=a.model,
                         depth=a.depth, time_limit=a.time_limit, min_random=a.min_random,
                         max_random=a.max_random, epsilon=a.epsilon, use_tt=not a.no_tt,
                         use_ordering=not a.no_ordering, seed=a.seed,
                         games_per_shard=a.games_per_shard, out_dir=a.out, workers=a.workers)
    return cfg, a.force


def main(argv=None) -> None:
    cfg, force = parse_args(argv)
    try:
        run(cfg, force=force)
    except KeyboardInterrupt:
        print("\nstopped. Finished shards are kept; run the same command to continue.",
              file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
