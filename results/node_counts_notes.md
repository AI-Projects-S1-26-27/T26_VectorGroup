# Node-count experiment: 2026-11-17

Owner: Rujuta Deshmukh, with OpenAI Codex assistance.

## Reproduce

```powershell
python -m eval.node_counts --depth 8 --time-limit 120 --count 100 --seed 26 --workers 3 --out results/node_counts.csv --summary results/node_counts_summary.json --plot results/plots/node_counts.png --progress
```

Environment: Windows 10.0.26200, Python 3.11.9 (64-bit), NumPy board API,
Matplotlib 3.10.3. Base repository commit: `2ca07b3`; experiment changes are
uncommitted on `rujuta/final-node-experiment` at preparation time.

The CSV contains 100 unique board positions and 400 rows. Move strings use
1-indexed columns; the empty string is the empty board. A seeded generator
cycles candidate lengths 0..24 and rejects finished games, immediate mover
wins, and duplicate board keys. Selection uses no search-performance results.
These synthetic positions are supplied by this experiment, not an external
proposal dataset. The original proposal was unavailable in the checkout.

Each configuration uses the same heuristic and existing alpha-beta search.
Baseline already uses centre-first ordering. The `tt` configuration also
benefits from search's existing table-move-first fallback. Tables start empty
for each configuration/position but persist across iterative-deepening rounds
within that search. Counts include all those rounds. No teammate modules
were modified for this experiment.

## Measured results

- All four configurations completed depth 8 on 82 positions.
- All four proved a result before depth 8 on 18 positions.
- No incomplete/time-limited positions; no score mismatches.
- Principal aggregate compares only the 82 positions with all four at depth 8.

| Configuration | Total nodes | Summed search seconds |
|---|---:|---:|
| Baseline | 5,934,640 | 966.99 |
| Ordering | 5,773,011 | 1,218.99 |
| Table | 2,561,761 | 368.55 |
| Table + ordering | 2,526,749 | 512.06 |

Baseline / combined node count = **2.3487x** (about **57.4% fewer nodes**).
Median of individual position ratios = **2.2133x**.
**The documented 10x reduction target was not met.**

The table produces most of the benefit. Ordering reduces nodes slightly but
adds Python tactical-check overhead. In this run the table alone was faster
than both hooks, despite exploring slightly more nodes. Three positions can
run concurrently, so summed durations are not total experiment elapsed time;
timings vary with machine load. Use `--workers 1` for isolated timing studies.

The raw CSV retains all early-solved positions. The plot deliberately uses
only the complete depth-8 subset. It is an aggregate plot for readability;
Mani's existing plotting script also accepts the raw CSV without modification.

## Checks and limitations

The CSV has exactly one row per position/configuration. Equal-depth root-best
scores agree. Focused module and integration tests: **27 passed**, including
warm-table root-score tests, seeded sample checks, output encoding/schema,
equal-depth summary rules, and serial/parallel node-count equivalence.
The earlier complete-suite attempt reported **144 passed, 5 skipped, 1 failed**
because `torch` is absent and a self-play test imports the network evaluator.

The baseline is not unpruned minimax, the sample is not representative human
play, and no confidence claim is made for the node ratio. The table uses
`Board.key()`, not Zobrist hashing; the team's hashing requirement still needs
confirmation. Results measure the existing implementation, not an optimised
native Connect-4 solver.
