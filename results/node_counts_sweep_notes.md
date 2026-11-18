# Fixed-depth search-efficiency sweep (2026-11-18)

Subsequent update: the complete depth-8 comparison is now saved separately in
`node_counts_depth8_complete.csv`; see `node_counts_depth8_complete_notes.md`.
It covers all 100 positions and meets the 10x node target. This earlier bounded
sweep remains unchanged as historical data; its depth-8 coverage is superseded.

Owner: Rujuta Deshmukh, with OpenAI Codex assistance.

## Purpose and reproducibility

The original proposal, section 4.5, requests minimax, alpha-beta, and optimized
alpha-beta at depths 4 through 12 on 100 fixed positions. The earlier
`node_counts.csv` measured four iterative-deepening alpha-beta configurations
at depth 8. It is retained unchanged and is not merged with this new protocol.

```powershell
python -m eval.node_counts --depths 4 5 6 7 8 9 10 11 12 --count 100 --seed 26 --workers 6 --node-limit 20000 --time-limit 10 --out results/node_counts_sweep.csv --summary results/node_counts_sweep_summary.json --plot results/plots/node_counts_sweep.png --progress
```

The exact same seed-26 positions as the original CSV are used at every depth;
no hard position was replaced to increase completion rates. There are 2,700
unique position/depth/configuration rows. The CSV is flushed per finished
attempt. The same command with `--resume` resumes interrupted files, requiring
matching sample/depths/limits. A completed limited attempt remains a limited
attempt on resume; it is not silently retried with different resource limits.
For longer runs choose a new output path and explicitly raise the limits.

Platform: Windows, Python 3.11.9. Six concurrent workers; no dedicated CPU
cores were reserved, so timings and time-limit outcomes depend on system load.
Node caps provide an additional deterministic bound. Base commit: `7678c43`,
plus uncommitted changes to Rujuta's benchmark, tests, and documentation.

## Shared rules and counting

- Single fixed-depth search per attempt, without iterative deepening.
- Root excluded from counts; each recursive negamax visit counts one node.
- All root moves receive full-window searches, so a completed row contains
  exact per-root-move scores under the selected horizon and heuristic.
- All paths retain the production full-board and immediate-win prechecks,
  including recognition of an immediate win before horizon evaluation. This
  common tactical-terminal shortcut is part of the experiment's definition.
- Minimax has no alpha-beta cutoffs, transposition reuse, or killer ordering.
- Alpha-beta reuses the production search helper unchanged, centre-first.
- Optimized adds Rujuta's ordering and a fresh transposition table. Tables are
  not shared across positions or depths.
- No early stop at the root merely because a forced result is found.
- Every attempt is capped at 20,000 recursive visits and 10 wall-clock seconds.
  Interrupted rows have completed_depth=0 and blank score/chosen/root_scores.
  Their node count is partial work, not the completed-tree node count.

No teammate files were edited. The production alpha-beta helper is reused
only by this experimental driver; it is cross-checked against public search
and unpruned minimax in tests.

## Results

1,315 of 2,700 attempts completed, 1,360 hit the node cap, and 25 hit the time
cap. Completed root-score vectors agree across available configurations.

| Depth | Minimax complete | Alpha-beta complete | Optimized complete |
|---|---:|---:|---:|
| 4 | 100 | 100 | 100 |
| 5 | 100 | 100 | 100 |
| 6 | 34 | 100 | 100 |
| 7 | 14 | 75 | 98 |
| 8 | 8 | 37 | 51 |
| 9 | 8 | 26 | 36 |
| 10 | 8 | 16 | 27 |
| 11 | 8 | 14 | 21 |
| 12 | 8 | 12 | 14 |

All counts are out of the same 100 positions.

| Depth (full sample) | Minimax nodes | Alpha-beta nodes | Optimized nodes | Minimax / optimized |
|---|---:|---:|---:|---:|
| 4 | 161,091 | 54,920 | 52,118 | 3.09x |
| 5 | 979,765 | 153,863 | 123,896 | 7.91x |

**The full numerical proposal experiment remains incomplete at depths 6-12.**
The code and all bounded attempts are complete, but limited rows do not fill
that gap. The 100-position depth-8 10x target is **not fully measured**.

Summary ratios use matching completed pairs only, never partial counts. Pair
coverage can differ between minimax/optimized and alpha-beta/optimized. The
summary also supplies totals for the all-three-complete subset at each depth.
Do not compare those changing subsets as if they were a fixed population.
At depth 8 and deeper the eight completed minimax positions are trivial
forced-loss positions under the shared immediate-win precheck: their total
count is only 61 per depth. Their 1x ratio says nothing about the unsolved
hard positions. Likewise, the above-10x depth-6/7 subset ratios do not establish
the target for 100 positions at depth 8.

The plot displays coverage alongside paired ratios. Solid ratio points/lines
cover all 100 positions; hollow, unconnected points use incomplete subsets.
All raw limited attempts are retained for auditing. No counts were estimated,
extrapolated, cached as if physically searched by minimax, or fabricated.

## Validation and continuation

Focused tests: 38 passed, including the 7+49 exact empty-board minimax node
count at depth 2, every-root-score agreement, comparison with public production
search at its actual depth, node/time interruption handling, complete-only
summary rules, corrupted-score detection, checkpoint/resume and CSV output.

Increasing limits for a new artifact is supported, e.g. `--node-limit 0
--time-limit 86400` permits uncapped-node searches with up to a day per attempt.
It does not ensure completion: plain minimax near the opening has exponential
growth. Reserve appropriate compute, and keep interrupted runs marked as such.
The old depth-8 study's 2.35x ratio is the extra benefit of hooks over existing
alpha-beta, not the overall minimax-to-optimized reduction promised in the
proposal. Report the two protocols separately.
