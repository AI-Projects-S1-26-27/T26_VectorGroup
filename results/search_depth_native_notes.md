# Opt-in native search-depth result (2026-11-18)

Owner: Rujuta Deshmukh, with OpenAI Codex assistance. Shridali's search
dispatcher was changed with the user's explicit permission. Board, evaluator,
trace, and ordering implementations were not changed. Existing Python search
remains the default and remains available as the fallback.

## Target and measured result

At least 10 completed plies per move with a one-second search budget, using
the heuristic evaluator on the original three measurement positions.

| Position | Exact move sequence | Runs | Completed depth range |
|---|---|---:|---:|
| Empty | empty string | 5 | 12 |
| Early | 332432 | 5 | 14-15 |
| Middle | 33243244152251 | 5 | 14 |

All 15 externally timed calls took less than one second. Maximum wall time:
**0.9721349000174087 seconds**. Minimum completed depth: **12**.
**The target is met for this prepared native configuration on these positions
and this workstation.** It is not a claim that the pure-Python path meets the
target, or that every position/machine will achieve the same depth.

Raw evidence: `results/search_depth_native.json`; figure:
`results/plots/search_depth_native.png`.

## Reproduce and use in the app

```powershell
python -m c4.native_search --backend native --repeats 5 --time-limit 1 --measure results/search_depth_native.json --plot results/plots/search_depth_native.png
```

This explicitly requires the native backend; a missing compiler is an error,
not a silent Python measurement. A g++/clang++ compiler is required at setup.
The tested compiler was MSYS2 g++ 15.2.0, with
`-static -O3 -march=native -std=c++17 -shared`. Generated DLLs/shared libraries
are cached in the OS temporary folder and are not committed.

To enable native acceleration for compatible heuristic searches in the app:

```powershell
python -c "from c4.native_search import prepare_native_search; prepare_native_search()"
$env:C4_SEARCH_BACKEND = 'auto'
python -m uvicorn web.app:app --reload
```

`auto` uses native search for the unchanged heuristic with supported table and
ordering, and falls back to Python if unavailable or incompatible. Network
and custom evaluator/ordering/table implementations stay on Python. Remove
the environment variable or use `C4_SEARCH_BACKEND=python` to select Python.
Direct calls can also use `search(..., backend='native')` or `backend='python'`.

## Budget and methodology

The exact position inputs consumed by `eval/measure_search.py` were retained;
the comment about zero-indexed columns was not used to reinterpret them.
Every call created a fresh evaluator and table. Runs were serial, with five
repetitions per position. A separate Python perf_counter measured the entire
public search call, including dispatch, context allocation, native execution,
and SearchTrace construction. Internal trace timings are also saved.

One-time compilation/loading is setup, analogous to importing the program or
loading model weights. It happens before per-move measurement. The saved
setup time was about 0.025 s from an already compiled cache; first-time source
compilation takes longer and was not measured as a one-second search. The
native runtime reserves 0.03 s of the requested budget for Python overhead and
scheduling noise, searching for at most the remaining budget. It does not
increase the one-second limit. Depth 1 always completes, matching Python.

Platform: Windows 10.0.26200, Python 3.11.9. No hardware-independent throughput
or CPU isolation guarantee is made. Native source SHA-256:
`f39c9838161ec63b4788bf7e038687eb36ae0da2c84fb76cf6c11ca5e6bb6e3d`.

## What is preserved and checked

The accelerator implements the existing negamax/alpha-beta algorithm and
iterative deepening, using full-window searches for **every legal root move**.
It retains the same 69-window heuristic, weights, perspective, clamp, terminal
prechecks, centre-first/tactical ordering, table flags and replacement policy,
win-distance normalization, and discard of incomplete iterations. It performs
no late-move reductions or selective horizon changes. The trace records actual
completed depth, all root scores, legal PVs, nodes, and measured time.

The Python TranspositionTable lazily attaches native storage when requested;
probe/store/clear/len/stats remain functional before and after migration.
Native table access is locked for thread safety, and clear resets its counters.
Native and Python share imported flag values checked at setup.

Validation in `results/native_search_validation.json` records:

- Identical heuristic scores on **4,198 legal positions**.
- All **100 fixed sample positions** checked: 82 completed depth-8 root-score
  vectors match the archived exhaustive results; 18 early-decided traces
  match Python search at their completed depth.
- Every checked PV step is legal.

The focused native/core suite passed **44 tests**. With automatic dispatch
enabled, the broader board/search/table/benchmark/agent/game/web/explanation/QA
suite passed **132 tests, 2 skipped**. Tests include cold/warm table use,
exact root scores and node counts, migration, eviction, counters, fallback,
custom evaluators, deadlines and terminal rejection. This is not a claim that
the entire repository suite, including unavailable torch dependencies, passed.

## Reporting qualification

This is a **native-accelerated implementation deviation** from the original
Python-only plan and must be disclosed. Report Python's earlier 7-9-ply result
separately from this native mode's 12-15 plies. Prior Python optimization
trials remain rolled back; they are not responsible for this pass.

Earlier match, network, and efficiency artifacts remain observations of their
recorded configurations. In particular, do not reuse the old network-vs-Python
heuristic match result as a match result against this accelerated engine.
Existing Python node-reduction figures are also not a native wall-time claim.

For the final report's search-depth row, use a qualified verdict such as:
"Native heuristic mode: target met (12-15 plies; 15/15 calls below 1 s after
setup). Original Python mode: target not met." No teammate report was rewritten
by this task; its owner should incorporate this result with the qualification.
