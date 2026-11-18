# Completed depth-8 search-efficiency comparison (2026-11-18)

Owner: Rujuta Deshmukh, with OpenAI Codex assistance.

## Result

All 100 original seed-26 positions completed for all three algorithms at fixed
depth 8: **300/300 complete, zero node-limited, zero time-limited**. Every root
score vector and chosen move agrees across configurations.

| Configuration | Actual visited nodes | Minimax / configuration |
|---|---:|---:|
| minimax | 217,990,090 | 1.00x |
| alpha-beta | 4,078,411 | 53.45x |
| alpha-beta+ordering+tt | 2,119,497 | 102.85x |

**The 10x depth-8 node-reduction target is met for this sample and protocol.**
The exact minimax/optimized ratio is 102.84991674911548. Optimized reduces nodes
by approximately 99.03% versus minimax. The separate alpha-beta/optimized ratio
is 1.9242353256456604. Do not confuse these baselines.

## Reproduce

```powershell
python -m eval.node_counts --depths 8 --count 100 --seed 26 --workers 4 --node-limit 0 --time-limit 3600 --native-minimax --out results/node_counts_depth8_complete.csv --summary results/node_counts_depth8_complete_summary.json --plot results/plots/node_counts_depth8_complete.png --progress
```

There is no node cap. A one-hour per-search safety deadline remains, but no
run reached it. Four independent workers ran on Windows/Python 3.11.9.
The exact same 100 positions as `node_counts.csv` and `node_counts_sweep.csv`
were used. None was replaced, dropped, or selected based on measured savings.
CSV fields identify the backend used in every row.

## Counting and backend validation

Every run searches a single fixed depth. There is no iterative deepening,
no early root-level stopping after proving a result, and no shared table
between configurations/positions. All root children use full windows. Root
is excluded from node counts. All three paths share production's full-board
and immediate-win prechecks, including immediate-win recognition before
horizon evaluation. They use the same heuristic and centre-first baseline.

Minimax uses a compiled C++ exhaustive traversal embedded in Rujuta's
`eval/node_counts.py`. It physically visits and counts every recursive node;
there is no alpha-beta pruning, transposition cache, memoized tree counting,
leaf-evaluation cache, or extrapolation. The optional native kernel only
accelerates execution of that traversal. Both alpha-beta variants remain the
unchanged production Python search helper; the optimized variant adds
Rujuta's existing ordering and a fresh table.

Compiler: MSYS2 g++ 15.2.0, `-static -O3 -march=native -std=c++17`. Kernel source
SHA-256: `cc47f735657bc082b7e4d58cf5d6c0ada4978e8e58e04df45ea35dcaf97898c3`.
Compilation artifacts stay in a temporary cache, not the repository. Other
machines need a compatible C++ compiler; the normal Python agent does not.

`results/native_minimax_validation.json` records **288 exact matches** against
every completed Python minimax row from the earlier sweep, including all
200 runs on the 100 positions at depths 4 and 5. Compared fields: node count,
chosen move, best score, root-score vector, status, completed depth. Native
and Python unit tests also cover full columns, immediate wins, threats,
limited-run handling, and parallel output. The focused suite passes 44 tests.
All 100 depth-8 root-score vectors also match both Python alpha-beta variants.

Since the execution languages differ, do **not** compare the runtime columns
as a fair algorithmic speed benchmark. This study establishes a node-count
reduction only. Runtime costs of the real Python agent are a separate study.
The common tactical-terminal shortcut is part of this benchmark's definition;
these counts are not for a completely naive tree generator.

## Relation to earlier results and report handoff

The old 2.35x result compared iterative-deepening alpha-beta with/without hooks.
It was not a minimax comparison and is not contradicted by the 102.85x result.
The new 1.92x hooks-only ratio is for a fresh, single-depth protocol and a full
100-position cohort. Keep the experiment definitions separate.

The bounded depth-4-12 sweep remains archived unchanged. This new artifact
supersedes its incomplete depth-8 coverage, not its measurements at other
depths. Full-sample comparisons at depths 6, 7, and 9-12 remain incomplete.

For Mani/Shridali's final report: replace the search-efficiency headline
"10x target not met, 2.35x" with the complete minimax comparison and its
documented native-backend qualification. Preserve the hook-only result as a
separate ablation. Do not claim that all depth-4-12 experiments are complete,
that timing improved 102.85x, or that this ratio applies to every position.
