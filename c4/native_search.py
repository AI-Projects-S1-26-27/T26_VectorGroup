"""Opt-in heuristic search accelerator. OWNER: Rujuta.

Compile once with prepare_native_search(); production Python remains available.
Native and Python use identical root windows, heuristic and table conventions.
"""
from __future__ import annotations

import ctypes as C
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from c4.board import Board, WIDTH, HEIGHT, H1, CENTER_FIRST
from c4.eval_heuristic import HeuristicEvaluator, WEIGHTS
from c4.trace import MoveInfo, SearchTrace, WIN_SCORE, MAX_HEURISTIC

_LIB = None
_LOAD_LOCK = threading.Lock()


class NativeUnavailable(RuntimeError):
    pass


class _Move(C.Structure):
    _fields_ = [("score", C.c_int), ("length", C.c_int), ("pv", C.c_int * 44)]


class _Result(C.Structure):
    _fields_ = [("status", C.c_int), ("depth", C.c_int), ("chosen", C.c_int),
                ("static_score", C.c_int), ("nodes", C.c_uint64), ("moves", _Move * 7)]


def source_digest():
    return hashlib.sha256(Path(__file__).with_suffix(".cpp").read_bytes()).hexdigest()


def prepare_native_search():
    """Compile/load outside the per-move clock, like loading model weights."""
    global _LIB
    with _LOAD_LOCK:
        if _LIB is not None:
            return _LIB
        from c4.search import EXACT, LOWER, UPPER
        if ((WIDTH, HEIGHT, H1, WIN_SCORE, MAX_HEURISTIC, WEIGHTS, tuple(CENTER_FIRST)) !=
            (7, 6, 7, 100000, 9999, (0, 1, 10, 50, 500), (3, 2, 4, 1, 5, 0, 6))):
            raise NativeUnavailable("Native constants differ from Python; update and revalidate")
        if (EXACT, LOWER, UPPER) != (0, 1, 2):
            raise NativeUnavailable("Native table flags differ from Python")
        compiler = shutil.which("g++") or shutil.which("clang++")
        candidate = Path("C:/msys64/mingw64/bin/g++.exe")
        if compiler is None and candidate.exists():
            compiler = str(candidate)
        if compiler is None:
            raise NativeUnavailable("Native backend needs g++/clang++; Python search is available")
        source = Path(__file__).with_suffix(".cpp")
        cache = Path(tempfile.gettempdir()) / "c4_native_search"
        cache.mkdir(parents=True, exist_ok=True)
        library = cache / (source_digest()[:20] + (".dll" if sys.platform == "win32" else ".so"))
        if not library.exists():
            output = cache / (library.stem + f"_{os.getpid()}" + library.suffix)
            command = [compiler, "-O3", "-march=native", "-std=c++17", "-shared",
                       str(source), "-o", str(output)]
            if sys.platform == "win32":
                command.insert(1, "-static")
            else:
                command.insert(1, "-fPIC")
            environment = dict(os.environ)
            environment["PATH"] = str(Path(compiler).parent) + os.pathsep + environment.get("PATH", "")
            try:
                subprocess.run(command, check=True, capture_output=True, text=True, env=environment)
                if library.exists():
                    output.unlink()
                else:
                    output.replace(library)
            except (OSError, subprocess.CalledProcessError) as error:
                raise NativeUnavailable(f"Cannot build native backend: {getattr(error, 'stderr', error)}") from error
        try:
            lib = C.CDLL(str(library))
        except OSError as error:
            raise NativeUnavailable(f"Cannot load native backend: {error}") from error
        signatures = {
            "c4_table_new": ([C.c_uint64], C.c_void_p),
            "c4_table_free": ([C.c_void_p], None),
            "c4_table_clear": ([C.c_void_p], None),
            "c4_table_probe": ([C.c_void_p, C.c_uint64, C.POINTER(C.c_int)], C.c_int),
            "c4_table_store": ([C.c_void_p, C.c_uint64, C.c_int, C.c_int, C.c_int, C.c_int], None),
            "c4_table_stats": ([C.c_void_p, C.POINTER(C.c_uint64)], None),
            "c4_table_counters": ([C.c_void_p, C.c_uint64, C.c_uint64, C.c_uint64], None),
            "c4_result_size": ([], C.c_uint64),
            "c4_evaluate": ([C.c_uint64, C.c_uint64], C.c_int),
            "c4_search": ([C.c_uint64, C.c_uint64, C.c_double, C.c_int,
                           C.c_void_p, C.c_int, C.POINTER(_Result)], C.c_int),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(lib, name)
            function.argtypes, function.restype = arguments, result
        if lib.c4_result_size() != C.sizeof(_Result):
            raise NativeUnavailable("Native/Python result layouts differ")
        _LIB = lib
        return lib


class NativeTable:
    def __init__(self, capacity):
        self.lib = prepare_native_search()
        self.lock = threading.RLock()
        self.handle = self.lib.c4_table_new(capacity)
        if not self.handle:
            raise MemoryError("Cannot allocate native transposition table")

    def __del__(self):
        handle = getattr(self, "handle", None)
        if handle:
            self.lib.c4_table_free(handle)
            self.handle = None

    def probe(self, key):
        with self.lock:
            out = (C.c_int * 4)()
            if not self.lib.c4_table_probe(self.handle, key, out):
                return None
            return (out[0], out[1], out[2], None if out[3] < 0 else out[3])

    def store(self, key, depth, value, flag, best_move):
        with self.lock:
            self.lib.c4_table_store(self.handle, key, depth, value, flag,
                                    -1 if best_move is None else best_move)

    def clear(self):
        with self.lock:
            self.lib.c4_table_clear(self.handle)

    def stats(self):
        with self.lock:
            out = (C.c_uint64 * 4)()
            self.lib.c4_table_stats(self.handle, out)
            return dict(zip(("entries", "probes", "hits", "stores"), out))


def native_search(board, evaluator, time_limit=1.0, max_depth=42, tt=None, order_fn=None):
    from c4.ordering import move_ordering
    from c4.tt import TranspositionTable
    if type(evaluator) is not HeuristicEvaluator:
        raise ValueError("Native backend supports the unchanged HeuristicEvaluator only")
    if tt is not None and type(tt) is not TranspositionTable:
        raise ValueError("Custom tables require the Python backend")
    if order_fn is not None and order_fn is not move_ordering:
        raise ValueError("Custom ordering requires the Python backend")
    if board.is_over():
        raise ValueError("cannot search a finished game")
    if max_depth < 1 or time_limit < 0:
        raise ValueError("invalid search limits")
    started = time.perf_counter()
    lib = prepare_native_search()
    context = tt.native_context() if tt is not None else None
    result = _Result()
    # Leave time for Python marshalling, trace construction, and scheduler noise.
    remaining = max(0.0, time_limit - (time.perf_counter() - started) - 0.03)
    if context is None:
        code = lib.c4_search(board.position, board.mask, remaining, max_depth, None,
                             order_fn is not None, C.byref(result))
    else:
        with context.lock:
            code = lib.c4_search(board.position, board.mask, remaining, max_depth, context.handle,
                                 order_fn is not None, C.byref(result))
    if code:
        raise RuntimeError(f"Native search failed with code {code}")
    infos = {}
    for col in board.legal_moves():
        move = result.moves[col]
        infos[col] = MoveInfo(col=col, score=move.score, depth=result.depth,
                              pv=list(move.pv[:move.length]))
    trace = SearchTrace(board=board, chosen=result.chosen, depth=result.depth, nodes=result.nodes,
                        time_s=0, evaluator=evaluator.name, static_score=result.static_score, moves=infos)
    trace.backend = "native"
    trace.time_s = time.perf_counter() - started
    return trace


def main(argv=None):
    """Measure prepared runtime on the original three positions, without torch."""
    import argparse
    import json
    import platform
    from c4.search import search
    from c4.tt import TranspositionTable
    from c4.ordering import move_ordering
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure", type=Path, default=Path("results/search_depth_native.json"))
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--time-limit", type=float, default=1.0)
    parser.add_argument("--backend", choices=("native", "python"), default="native")
    parser.add_argument("--plot", type=Path)
    args = parser.parse_args(argv)
    if args.repeats < 1 or args.time_limit <= 0:
        parser.error("repeats and time limit must be positive")
    setup = time.perf_counter()
    if args.backend == "native":
        prepare_native_search()
    setup_seconds = time.perf_counter() - setup
    positions = {"empty": "", "early": "332432", "middle": "33243244152251"}
    rows = []
    for repeat in range(args.repeats):
        for name, sequence in positions.items():
            board, evaluator, table = Board.from_moves(sequence), HeuristicEvaluator(), TranspositionTable()
            started = time.perf_counter()
            trace = search(board, evaluator, time_limit=args.time_limit,
                           tt=table, order_fn=move_ordering, backend=args.backend)
            elapsed = time.perf_counter() - started
            row = dict(repeat=repeat+1, position=name, moves=sequence,
                       depth=trace.depth, nodes=trace.nodes, time_s=trace.time_s,
                       wall_time_s=elapsed, chosen=trace.chosen, score=trace.score,
                       backend=getattr(trace, "backend", "python"),
                       root_scores={c: m.score for c, m in trace.moves.items()},
                       table=table.stats())
            rows.append(row)
            print(f"{repeat+1} {name}: depth {trace.depth}, wall {elapsed:.6f}s", flush=True)
    report = dict(backend=args.backend, positions=positions, repeats=args.repeats,
                  time_limit_s=args.time_limit, setup_time_s=setup_seconds,
                  setup_excluded_from_per_move_clock=True, cold_table_each_call=True,
                  native_source_sha256=source_digest() if args.backend == "native" else None,
                  python=platform.python_version(), platform=platform.platform(),
                  target_met=all(r["depth"] >= 10 and r["wall_time_s"] <= args.time_limit for r in rows),
                  minimum_depth=min(r["depth"] for r in rows),
                  maximum_wall_time_s=max(r["wall_time_s"] for r in rows), rows=rows)
    args.measure.parent.mkdir(parents=True, exist_ok=True)
    args.measure.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    if args.plot:
        plot_depth_results(report, args.plot)
    print(f"All-run target met: {report['target_met']}")


def plot_depth_results(report, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = list(report["positions"])
    lows = [min(r["depth"] for r in report["rows"] if r["position"] == name) for name in names]
    highs = [max(r["depth"] for r in report["rows"] if r["position"] == name) for name in names]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(names, lows, color="#315391")
    ax.errorbar(names, lows, yerr=[[0]*len(names), [b-a for a,b in zip(lows, highs)]],
                fmt="none", color="#172b4d", capsize=8)
    for index, (low, high) in enumerate(zip(lows, highs)):
        ax.annotate(str(low) if low == high else f"{low}-{high}", (index, high),
                    xytext=(0, 7), textcoords="offset points", ha="center")
    ax.axhline(10, color="#b8562b", linestyle="--", label="10-ply target")
    ax.set(ylabel="Completed plies", ylim=(0, max(highs)+2),
           title=f"Prepared {report['backend']} search at {report['time_limit_s']:g} second per move")
    ax.legend(loc="upper left")
    fig.text(0.5, 0.02,
             f"{len(report['rows'])} runs; fresh table each call; max wall {report['maximum_wall_time_s']:.4f}s",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
