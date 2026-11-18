"""Compare search nodes at equal depth: python -m eval.node_counts --depth 4.

Each position/configuration gets a fresh table. Timed-out or early-decided runs
report the actual completed depth, so their node totals can be interpreted.
"""
import argparse
import csv
import json
import os
import random
import statistics
import sys
import time
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from c4.board import Board, CENTER_FIRST, SIZE, WIDTH, HEIGHT, H1
from c4.eval_heuristic import HeuristicEvaluator, WEIGHTS
from c4.ordering import move_ordering
from c4.search import search, _Searcher, _TimeUp, INF
from c4.tt import TranspositionTable
from c4.trace import is_decided, WIN_SCORE, MAX_HEURISTIC

DEFAULT_POSITIONS = ("", "4453", "334455")
CONFIGURATIONS = ("baseline", "ordering", "tt", "tt+ordering")
SWEEP_CONFIGURATIONS = ("minimax", "alpha-beta", "alpha-beta+ordering+tt")
SWEEP_FIELDS = ("position", "configuration", "requested_depth", "completed_depth",
                "status", "nodes", "time_s", "chosen", "score", "tt_hits",
                "root_scores", "node_limit", "time_limit_s", "backend")


# Count an actual exhaustive traversal, not a cached or extrapolated tree.
# Native compilation is optional and affects minimax only, never production play.
_NATIVE_MINIMAX_SOURCE = r'''
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>
using U = uint64_t;
const int order[7] = {3,2,4,1,5,0,6};
const int weights[5] = {0,1,10,50,500};
std::vector<U> windows;
U nodes=0, cap=0;
double seconds=0;
auto started=std::chrono::steady_clock::now();
struct Limit { const char* status; };
bool alignment(U b) {
    for (int shift: {7,6,8,1}) {
        U m=b & (b>>shift);
        if (m & (m>>(2*shift))) return true;
    }
    return false;
}
bool legal(U mask,int c) { return !(mask & (U(1)<<(7*c+5))); }
U drop(U mask,int c) { return (mask+(U(1)<<(7*c))) & (U(63)<<(7*c)); }
bool wins(U pos,U mask,int c) { return alignment(pos | drop(mask,c)); }
int evaluate(U pos,U mask) {
    U opp=pos^mask, centre=U(63)<<21;
    int value=3*(__builtin_popcountll(pos&centre)-__builtin_popcountll(opp&centre));
    for (U w:windows) {
        int us=__builtin_popcountll(pos&w), them=__builtin_popcountll(opp&w);
        if (!them) value+=weights[us];
        if (!us) value-=weights[them];
    }
    for (int c:order) if (legal(mask,c))
        value+=200*(int(wins(pos,mask,c))-int(wins(opp,mask,c)));
    return std::max(-9999,std::min(9999,value));
}
int minimax(U pos,U mask,int depth,int ply) {
    if (cap && nodes>=cap) throw Limit{"node_limit"};
    if (nodes%1024==0 && seconds>0 &&
        std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count()>=seconds)
        throw Limit{"time_limit"};
    ++nodes;
    bool any=false;
    for (int c:order) if (legal(mask,c)) {
        any=true;
        if (wins(pos,mask,c)) return 100000-(ply+1);
    }
    if (!any) return 0;
    if (!depth) return evaluate(pos,mask);
    int best=-101000;
    for (int c:order) if (legal(mask,c)) {
        U childmask=mask | (mask+(U(1)<<(7*c)));
        int value=-minimax(pos^mask,childmask,depth-1,ply+1);
        if (value>best) best=value;
    }
    return best;
}
int main(int argc,char** argv) {
    if (argc!=5) return 2;
    int depth=std::stoi(argv[2]);
    if (depth<1 || depth>12) return 2;
    cap=std::stoull(argv[3]); seconds=std::stod(argv[4]);
    for (int c=0;c<7;++c) for (int r=0;r<6;++r)
        for (auto delta: {std::pair<int,int>{1,0},{0,1},{1,1},{1,-1}}) {
            int dc=delta.first, dr=delta.second;
            if (c+3*dc>=0 && c+3*dc<7 && r+3*dr>=0 && r+3*dr<6) {
                U w=0;
                for(int i=0;i<4;++i) w |= U(1)<<((c+i*dc)*7+r+i*dr);
                windows.push_back(w);
            }
        }
    U pos=0,mask=0;
    for(char ch:std::string(argv[1])) {
        int c=ch-'1';
        if(c<0 || c>6 || !legal(mask,c)) return 2;
        pos^=mask; mask |= mask+(U(1)<<(7*c));
    }
    int scores[7],best=-101000,chosen=-1;
    const char* status="complete";
    started=std::chrono::steady_clock::now();
    try {
        for(int c:order) if(legal(mask,c)) {
            scores[c]=wins(pos,mask,c) ? 99999 :
                -minimax(pos^mask,mask | (mask+(U(1)<<(7*c))),depth-1,1);
            if(scores[c]>best) { best=scores[c];chosen=c; }
        }
    } catch(Limit limit) { status=limit.status; }
    std::cout<<"{\"status\":\""<<status<<"\",\"nodes\":"<<nodes<<",\"root_scores\":{";
    bool first=true;
    if(std::string(status)=="complete") for(int c=0;c<7;++c) if(legal(mask,c)) {
        if(!first) std::cout<<",";
        first=false;
        std::cout<<"\""<<c<<"\":"<<scores[c];
    }
    std::cout<<"},\"chosen\":"<<chosen<<",\"score\":"<<best<<"}\n";
}
'''


def build_native_minimax(compiler=None):
    """Compile the optional exhaustive minimax counter into a temporary cache."""
    if ((WIDTH, HEIGHT, H1, WIN_SCORE, MAX_HEURISTIC, WEIGHTS, tuple(CENTER_FIRST)) !=
        (7, 6, 7, 100000, 9999, (0, 1, 10, 50, 500), (3, 2, 4, 1, 5, 0, 6))):
        raise RuntimeError("native kernel constants differ from Python; update and revalidate it")
    compiler = compiler or shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        candidate = Path("C:/msys64/mingw64/bin/g++.exe")
        compiler = str(candidate) if candidate.exists() else None
    if compiler is None:
        raise RuntimeError("native minimax requires g++ or clang++; use Python otherwise")
    cache = Path(tempfile.gettempdir()) / "c4_native_minimax"
    cache.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(_NATIVE_MINIMAX_SOURCE.encode()).hexdigest()[:16]
    executable = cache / (digest + (".exe" if sys.platform == "win32" else ""))
    if not executable.exists():
        source = cache / (digest + ".cpp")
        source.write_text(_NATIVE_MINIMAX_SOURCE, encoding="utf-8")
        command = [compiler, "-O3", "-march=native", "-std=c++17", str(source), "-o", str(executable)]
        if sys.platform == "win32":
            command.insert(1, "-static")
        compiler_env = dict(os.environ)
        compiler_env["PATH"] = str(Path(compiler).parent) + os.pathsep + compiler_env.get("PATH", "")
        subprocess.run(command, check=True, capture_output=True, text=True, env=compiler_env)
    return str(executable)


def native_minimax_run(moves, depth, node_limit, time_limit, executable):
    board = Board.from_moves(moves)
    if board.is_over() or not 1 <= depth <= min(12, SIZE-board.num_moves):
        raise ValueError("invalid native minimax position/depth")
    if (node_limit is not None and node_limit < 1) or time_limit <= 0:
        raise ValueError("invalid resource limits")
    start = time.perf_counter()
    result = subprocess.run([executable, moves, str(depth), str(node_limit or 0), str(time_limit)],
                            check=True, capture_output=True, text=True)
    value = json.loads(result.stdout)
    complete = value["status"] == "complete"
    return dict(position=moves, configuration="minimax", requested_depth=depth,
                completed_depth=depth if complete else 0, status=value["status"],
                nodes=value["nodes"], time_s=time.perf_counter()-start,
                chosen=value["chosen"] if complete else None,
                score=value["score"] if complete else None, tt_hits=0,
                root_scores=json.dumps(value["root_scores"], sort_keys=True) if complete else "",
                node_limit=node_limit, time_limit_s=time_limit, backend="native_minimax")


def verify_native_against_csv(path, executable):
    """Cross-check native traversal against saved, complete Python measurements."""
    with Path(path).open(encoding="utf-8", newline="") as stream:
        rows = [r for r in csv.DictReader(stream) if r["configuration"] == "minimax"
                and r["status"] == "complete" and r.get("backend", "python") == "python"]
    if not rows:
        raise ValueError("no complete Python minimax rows to validate")
    fields = ("status", "nodes", "chosen", "score", "root_scores", "completed_depth")
    for saved in rows:
        native = native_minimax_run(saved["position"], int(saved["requested_depth"]),
                                    None, 3600, executable)
        for field in fields:
            if str(native[field]) != str(saved[field]):
                raise AssertionError((saved["position"], saved["requested_depth"], field))
    return dict(reference_csv=str(path), matched_runs=len(rows), compared_fields=list(fields),
                requested_depths=sorted({int(r["requested_depth"]) for r in rows}),
                native_source_sha256=hashlib.sha256(_NATIVE_MINIMAX_SOURCE.encode()).hexdigest(),
                all_matched=True)


def _sweep_job(moves, depth, configuration, node_limit, time_limit, native_executable):
    if configuration == "minimax" and native_executable:
        return native_minimax_run(moves, depth, node_limit, time_limit, native_executable)
    return fixed_depth_run(moves, depth, configuration, node_limit, time_limit)


class _NodeLimit(Exception):
    pass


class _BenchmarkSearcher(_Searcher):
    """Use production alpha-beta unchanged, or remove only alpha-beta cutoffs.

    The minimax path has no cache or pruning. Both retain the production
    terminal/immediate-win checks and evaluate the same horizon boards.
    """
    def __init__(self, configuration, node_limit):
        super().__init__(HeuristicEvaluator(),
                         TranspositionTable() if configuration.endswith("+tt") else None,
                         move_ordering if configuration.endswith("+tt") else None)
        self.configuration = configuration
        self.node_limit = node_limit

    def negamax(self, board, depth, alpha, beta, ply):
        if self.node_limit is not None and self.nodes >= self.node_limit:
            raise _NodeLimit
        if self.nodes % 64 == 0 and time.perf_counter() >= self.deadline:
            raise _TimeUp
        if self.configuration != "minimax":
            return super().negamax(board, depth, alpha, beta, ply)
        self.nodes += 1
        moves = [c for c in CENTER_FIRST if board.can_play(c)]
        if not moves:
            return 0
        if any(board.wins_by_playing(c) for c in moves):
            return WIN_SCORE - (ply + 1)
        if depth == 0:
            return self.evaluator.evaluate(board)
        return max(-self.negamax(board.play_unchecked(c), depth - 1,
                                 -INF, INF, ply + 1) for c in moves)


def fixed_depth_run(moves, depth, configuration, node_limit=20_000, time_limit=10.0):
    """One fresh, single-depth search; root children have full windows.

    Root is excluded from nodes to match production search. No iterative
    deepening and no early stopping merely because one root score is decided.
    On interruption, omit all scores/moves rather than return a partial result.
    """
    if configuration not in SWEEP_CONFIGURATIONS:
        raise ValueError("unknown sweep configuration")
    if not 1 <= depth <= SIZE or (node_limit is not None and node_limit < 1):
        raise ValueError("invalid depth or node limit")
    if time_limit <= 0:
        raise ValueError("time_limit must be positive")
    board = Board.from_moves(moves)
    if board.is_over():
        raise ValueError("finished benchmark position")
    if depth > SIZE - board.num_moves:
        raise ValueError("requested depth exceeds remaining playable cells")
    worker = _BenchmarkSearcher(configuration, node_limit)
    start = time.perf_counter()
    worker.deadline = start + time_limit
    status, scores = "complete", {}
    try:
        for col in CENTER_FIRST:
            if not board.can_play(col):
                continue
            if board.wins_by_playing(col):
                scores[col] = WIN_SCORE - 1
            else:
                scores[col] = -worker.negamax(board.play_unchecked(col), depth - 1,
                                               -INF, INF, 1)
    except _NodeLimit:
        status = "node_limit"
    except _TimeUp:
        status = "time_limit"
    complete = status == "complete"
    chosen = max(scores, key=scores.get) if complete else None
    return dict(position=moves, configuration=configuration,
                requested_depth=depth, completed_depth=depth if complete else 0,
                status=status, nodes=worker.nodes, time_s=time.perf_counter() - start,
                chosen=chosen, score=scores[chosen] if complete else None,
                tt_hits=worker.tt.stats()["hits"] if worker.tt is not None else 0,
                root_scores=json.dumps(scores, sort_keys=True) if complete else "",
                node_limit=node_limit, time_limit_s=time_limit, backend="python")


def summarize_sweep(rows):
    """Paired complete-only ratios; incomplete totals are never extrapolated."""
    if not rows:
        raise ValueError("cannot summarize an empty sweep")
    groups = {}
    for row in rows:
        key = (int(row["requested_depth"]), row["position"])
        group = groups.setdefault(key, {})
        if row["configuration"] in group:
            raise ValueError("duplicate sweep row")
        group[row["configuration"]] = row
    result = {}
    for depth in sorted({key[0] for key in groups}):
        depth_groups = [(pos, g) for (d, pos), g in groups.items() if d == depth]
        for _, group in depth_groups:
            if set(group) != set(SWEEP_CONFIGURATIONS):
                raise ValueError("missing sweep configurations")
        mismatches = []
        for pos, group in depth_groups:
            completed = [r for r in group.values() if r["status"] == "complete"]
            if len({r["root_scores"] for r in completed}) > 1:
                mismatches.append(pos)
        pairs = {}
        for baseline in ("minimax", "alpha-beta"):
            optimized = "alpha-beta+ordering+tt"
            paired = [g for _, g in depth_groups if
                      g[baseline]["status"] == g[optimized]["status"] == "complete"
                      and g[baseline]["root_scores"] == g[optimized]["root_scores"]]
            numerator = sum(int(g[baseline]["nodes"]) for g in paired)
            denominator = sum(int(g[optimized]["nodes"]) for g in paired)
            pairs[baseline] = dict(positions=len(paired), baseline_nodes=numerator,
                                   optimized_nodes=denominator,
                                   reduction=numerator / denominator if denominator else None)
        all_complete = [g for _, g in depth_groups if
                        all(r["status"] == "complete" for r in g.values())
                        and len({r["root_scores"] for r in g.values()}) == 1]
        result[str(depth)] = dict(positions=len(depth_groups),
            all_complete_positions=len(all_complete),
            all_complete_nodes={c: sum(int(g[c]["nodes"]) for g in all_complete)
                                for c in SWEEP_CONFIGURATIONS},
            complete={c: sum(g[c]["status"] == "complete" for _, g in depth_groups)
                      for c in SWEEP_CONFIGURATIONS},
            node_limited={c: sum(g[c]["status"] == "node_limit" for _, g in depth_groups)
                          for c in SWEEP_CONFIGURATIONS},
            time_limited={c: sum(g[c]["status"] == "time_limit" for _, g in depth_groups)
                          for c in SWEEP_CONFIGURATIONS},
            root_score_mismatches=mismatches, paired_comparisons=pairs)
    depth8 = result.get("8")
    coverage = depth8["all_complete_positions"] if depth8 else 0
    target = dict(depth=8, required_positions=100, required_reduction=10,
                  status="not_fully_measured", reference="minimax vs optimized")
    if depth8 and coverage == 100:
        ratio = depth8["paired_comparisons"]["minimax"]["reduction"]
        target["status"] = "met" if ratio is not None and ratio >= 10 else "not_met"
    return dict(method="single fixed depth; all root moves exact; root excluded from nodes",
                depths=result,
                proposal_depth8_target=target,
                fully_completed=all(r["status"] == "complete" for r in rows),
                scores_consistent=not any(d["root_score_mismatches"] for d in result.values()))


def plot_sweep(summary, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    depths = list(map(int, summary["depths"]))
    if len(depths) == 1:
        data = summary["depths"][str(depths[0])]
        fig, ax = plt.subplots(figsize=(9, 5))
        values = [data["all_complete_nodes"][c] for c in SWEEP_CONFIGURATIONS]
        labels = ("Plain minimax", "Alpha-beta", "Alpha-beta + ordering + TT")
        ax.bar(labels, values, color=("#65748b", "#35a0a3", "#315391"))
        ax.set_yscale("log")
        ax.set_ylabel("Nodes visited (log scale; root excluded)")
        ax.set_title(f"Depth {depths[0]}: {data['all_complete_positions']} fully compared positions")
        for i, value in enumerate(values):
            if value:
                ax.annotate(f"{value:,}", (i, value), xytext=(0, 6),
                            textcoords="offset points", ha="center")
        if max(values, default=0):
            ax.set_ylim(max(1, min(v for v in values if v) / 3), max(values) * 3)
        ratio = data["paired_comparisons"]["minimax"]["reduction"]
        caption = (f"Minimax / optimized = {ratio:.2f}x; target = 10x"
                   if ratio is not None else "No completed paired comparison")
        fig.text(0.5, 0.05, caption, ha="center")
        fig.text(0.5, 0.01, "Node comparison only; per-row backends are recorded in the CSV; identical scoring rules",
                 ha="center", fontsize=8)
        fig.tight_layout(rect=(0, 0.09, 1, 1))
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(destination, dpi=180)
        plt.close(fig)
        return
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for config in SWEEP_CONFIGURATIONS:
        axes[0].plot(depths, [summary["depths"][str(d)]["complete"][config]
                             for d in depths], marker="o", label=config)
    axes[0].set(xlabel="Requested depth", ylabel="Completed positions",
                title="Coverage (limited searches excluded from ratios)")
    axes[0].legend(fontsize=8)
    for baseline in ("minimax", "alpha-beta"):
        values = [summary["depths"][str(d)]["paired_comparisons"][baseline]["reduction"]
                  for d in depths]
        coverage = [summary["depths"][str(d)]["paired_comparisons"][baseline]["positions"]
                    == summary["depths"][str(d)]["positions"] for d in depths]
        line, = axes[1].plot(depths, [v if full else None for v, full in zip(values, coverage)],
                             marker="o", label=f"{baseline} / optimized")
        partial = [(d, v) for d, v, full in zip(depths, values, coverage)
                   if not full and v is not None]
        if partial:
            axes[1].scatter([d for d, _ in partial], [v for _, v in partial],
                            facecolors="none", edgecolors=line.get_color())
    axes[1].axhline(10, color="grey", linestyle="--", label="10x reference")
    axes[1].set(xlabel="Requested depth", ylabel="Node reduction (paired complete runs)",
                title="Solid: full sample; hollow: incomplete subsets", yscale="log")
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=180)
    plt.close(fig)


def run_sweep(positions, depths, out, workers=1, node_limit=20_000,
              time_limit=10.0, progress=False, resume=False, native_executable=None):
    """Checkpoint each completed job; resume only matching experiment settings."""
    positions, depths = tuple(positions), tuple(depths)
    if not positions or len(set(positions)) != len(positions):
        raise ValueError("positions must be nonempty and unique")
    if not depths or len(set(depths)) != len(depths) or any(not 1 <= d <= SIZE for d in depths):
        raise ValueError("depths must be unique and between 1 and 42")
    if workers < 1 or time_limit <= 0 or (node_limit is not None and node_limit < 1):
        raise ValueError("invalid resource limits")
    for moves in positions:
        board = Board.from_moves(moves)
        if board.is_over() or max(depths) > SIZE - board.num_moves:
            raise ValueError("invalid position for requested sweep depths")
    jobs = [(moves, depth, c) for depth in depths for moves in positions
            for c in SWEEP_CONFIGURATIONS]
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if resume and out.exists():
        with out.open(encoding="utf-8", newline="") as stream:
            existing = list(csv.DictReader(stream))
        allowed = set(jobs)
        for row in existing:
            row.setdefault("backend", "python")
            backend = "native_minimax" if native_executable and row["configuration"] == "minimax" else "python"
            if ((row["position"], int(row["requested_depth"]), row["configuration"]) not in allowed
                or int(row["node_limit"] or 0) != (node_limit or 0)
                or float(row["time_limit_s"]) != time_limit or row["backend"] != backend):
                raise ValueError("resume CSV does not match sample/depths/limits")
    seen = {(r["position"], int(r["requested_depth"]), r["configuration"]) for r in existing}
    if len(seen) != len(existing):
        raise ValueError("duplicate resume rows")
    pending = [job for job in jobs if job not in seen]
    rows = list(existing)
    with out.open("a" if existing else "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SWEEP_FIELDS)
        if not existing:
            writer.writeheader()
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_sweep_job, *job, node_limit, time_limit, native_executable): job
                       for job in pending}
            for future in as_completed(futures):
                row = future.result()
                rows.append(row)
                writer.writerow(row)
                stream.flush()
                if progress and (len(rows) % 30 == 0 or len(rows) == len(jobs)):
                    print(f"Saved {len(rows)}/{len(jobs)} search runs", file=sys.stderr, flush=True)
    # Keep the saved artifact deterministic in order, independent of worker completion.
    order = {job: i for i, job in enumerate(jobs)}
    rows.sort(key=lambda r: order[(r["position"], int(r["requested_depth"]), r["configuration"])])
    with out.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SWEEP_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


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
    parser.add_argument("--depths", nargs="+", type=int,
                        help="fixed-depth proposal sweep, e.g. --depths 4 5 6 7 8 9 10 11 12")
    parser.add_argument("--node-limit", type=int, default=20_000,
                        help="per-search sweep node limit; 0 disables it")
    parser.add_argument("--native-minimax", action="store_true",
                        help="compile an equivalent exhaustive minimax counter; do not compare runtimes")
    parser.add_argument("--resume", action="store_true",
                        help="resume an interrupted fixed-depth sweep CSV")
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
    if args.depths:
        if args.out is None or args.node_limit < 0:
            parser.error("sweep requires --out and a nonnegative node-limit")
        native_executable = build_native_minimax() if args.native_minimax else None
        rows = run_sweep(positions, args.depths, args.out, args.workers,
                         args.node_limit or None, args.time_limit, args.progress, args.resume,
                         native_executable)
        summary = summarize_sweep(rows)
        summary.update(seed=args.seed if args.positions is None else None,
                       workers=args.workers, node_limit=args.node_limit or None,
                       time_limit_s=args.time_limit,
                       minimax_backend="native_minimax" if native_executable else "python")
        if native_executable:
            summary["native_source_sha256"] = hashlib.sha256(_NATIVE_MINIMAX_SOURCE.encode()).hexdigest()
        if args.summary:
            args.summary.parent.mkdir(parents=True, exist_ok=True)
            args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        if args.plot:
            plot_sweep(summary, args.plot)
        return
    if args.resume:
        parser.error("--resume requires --depths")
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
