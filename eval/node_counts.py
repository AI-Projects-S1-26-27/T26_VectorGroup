"""Compare search nodes at equal depth: python -m eval.node_counts --depth 4.

Each position/configuration gets a fresh table. Timed-out or early-decided runs
report the actual completed depth, so their node totals can be interpreted.
"""
import argparse
import csv
import json
import random
import statistics
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

from c4.board import Board
from c4.eval_heuristic import HeuristicEvaluator
from c4.ordering import move_ordering
from c4.search import search
from c4.tt import TranspositionTable
from c4.trace import is_decided

DEFAULT_POSITIONS = ("", "4453", "334455")
CONFIGURATIONS = ("baseline", "ordering", "tt", "tt+ordering")


def summarize_node_counts(rows):
    """Compare only complete, equal-depth groups; retain exclusion counts."""
    groups = {}
    for row in rows:
        group = groups.setdefault(row["position"], {})
        if row["configuration"] in group:
            raise ValueError("duplicate position/configuration")
        group[row["configuration"]] = row
    complete, early, incomplete = [], 0, 0
    score_mismatches = []
    for position, group in groups.items():
        if set(group) != set(CONFIGURATIONS):
            raise ValueError("each position must have all four configurations")
        requested = {int(r["requested_depth"]) for r in group.values()}
        if len(requested) != 1:
            raise ValueError("requested depths must match within each position")
        target = next(iter(requested))
        depths = {int(r["completed_depth"]) for r in group.values()}
        if len(depths) == 1 and len({int(r["score"]) for r in group.values()}) != 1:
            score_mismatches.append(position)
        if depths == {target}:
            complete.append(group)
        elif all(is_decided(int(r["score"])) for r in group.values()):
            early += 1
        else:
            incomplete += 1
    totals = {c: sum(int(g[c]["nodes"]) for g in complete) for c in CONFIGURATIONS}
    seconds = {c: sum(float(g[c]["time_s"]) for g in complete) for c in CONFIGURATIONS}
    ratios = [int(g["baseline"]["nodes"]) / int(g["tt+ordering"]["nodes"])
              for g in complete]
    reduction = totals["baseline"] / totals["tt+ordering"] if complete else None
    return dict(positions=len(groups),
                requested_depths=sorted({int(r["requested_depth"]) for r in rows}),
                full_depth_positions=len(complete),
                early_decided_positions=early, incomplete_positions=incomplete,
                score_mismatch_positions=score_mismatches,
                total_nodes=totals, total_time_s=seconds,
                aggregate_node_reduction=reduction,
                median_position_reduction=statistics.median(ratios) if ratios else None,
                target_reduction=10,
                target_met=reduction >= 10 if reduction is not None else None)


def plot_node_counts_summary(summary, destination):
    """Standalone report plot for the equal-depth subset, without editing Mani's code."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    values = [summary["total_nodes"][c] for c in CONFIGURATIONS]
    ax.bar(CONFIGURATIONS, values, color=("#65748b", "#35a0a3", "#5086c6", "#315391"))
    for i, value in enumerate(values):
        ax.annotate(f"{value:,}", (i, value), xytext=(0, 5),
                    textcoords="offset points", ha="center", fontsize=9)
    ax.set_ylabel("Total nodes, including iterative deepening")
    depths = ', '.join(map(str, summary['requested_depths']))
    ax.set_title(f"Search hooks at depth {depths}: {summary['full_depth_positions']} positions")
    ax.set_ylim(0, max(values, default=0) * 1.2 or 1)
    reduction = summary["aggregate_node_reduction"]
    caption = (f"Baseline / both hooks = {reduction:.2f}x; target = 10x"
               if reduction is not None else "No complete equal-depth comparisons")
    fig.text(0.5, 0.02, caption, ha="center")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(destination, dpi=180)
    plt.close(fig)


def fixed_positions(count=100, seed=26):
    """Seeded legal, unique positions sampled without consulting search results.

    Cycle target lengths 0..24. Reject finished games and immediate mover wins
    to avoid spending the benchmark on trivial one-ply decisions.
    """
    if not 1 <= count <= 1000:
        raise ValueError("count must be between 1 and 1000")
    rng = random.Random(seed)
    positions, keys = [], set()
    attempts = 0
    while len(positions) < count:
        length = attempts % 25
        attempts += 1
        board, moves = Board.empty(), ""
        for _ in range(length):
            if board.is_over():
                break
            col = rng.choice(board.legal_moves())
            board = board.play(col)
            moves += str(col + 1)
        if board.is_over() or board.winning_moves() or board.key() in keys:
            continue
        keys.add(board.key())
        positions.append(moves)
    return tuple(positions)


def _position_job(args):
    moves, depth, time_limit = args
    return compare_node_counts((moves,), depth, time_limit)


def compare_node_counts(positions=DEFAULT_POSITIONS, depth=4, time_limit=60.0,
                        progress=False, workers=1):
    """Return CSV-ready rows for baseline, ordering, table, and both hooks."""
    if depth < 1 or time_limit <= 0 or workers < 1:
        raise ValueError("depth, time_limit and workers must be positive")
    positions = tuple(positions)
    if workers > 1:
        rows = []
        jobs = ((moves, depth, time_limit) for moves in positions)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for index, result in enumerate(pool.map(_position_job, jobs), 1):
                rows.extend(result)
                if progress:
                    print(f"Completed {index}/{len(positions)} positions",
                          file=sys.stderr, flush=True)
        return rows
    rows = []
    for moves in positions:
        if progress:
            print(f"Position {len(rows) // 4 + 1}: {moves or '(empty)'}",
                  file=sys.stderr, flush=True)
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
    parser.add_argument("--positions", nargs="+", default=None,
                        help="1-indexed move strings; use an empty string for the opening")
    parser.add_argument("--count", type=int, default=100,
                        help="number of seeded positions when --positions is omitted")
    parser.add_argument("--seed", type=int, default=26)
    parser.add_argument("--out", type=Path, help="write UTF-8 CSV directly to this file")
    parser.add_argument("--summary", type=Path, help="write equal-depth statistics as JSON")
    parser.add_argument("--plot", type=Path, help="write the equal-depth node comparison PNG")
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--workers", type=int, default=1,
                        help="independent position workers; node totals are primary, not timing")
    args = parser.parse_args(argv)
    if args.depth < 1 or args.time_limit <= 0 or args.workers < 1:
        parser.error("depth, time-limit and workers must be positive")
    if not 1 <= args.count <= 1000:
        parser.error("count must be between 1 and 1000")
    positions = args.positions if args.positions is not None else fixed_positions(args.count, args.seed)
    rows = compare_node_counts(positions, args.depth, args.time_limit, args.progress, args.workers)
    def write_csv(stream):
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="") as stream:
            write_csv(stream)
    else:
        write_csv(sys.stdout)
    if args.summary or args.plot:
        summary = summarize_node_counts(rows)
        summary.update(seed=args.seed if args.positions is None else None,
                       time_limit_s=args.time_limit, workers=args.workers)
        if args.summary:
            args.summary.parent.mkdir(parents=True, exist_ok=True)
            args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        if args.plot:
            plot_node_counts_summary(summary, args.plot)


if __name__ == "__main__":
    main()
