# Testing and evaluation

## Scope

Mani's modules are `eval/solver.py`, `eval/match.py`, `eval/solver_agreement.py`, `eval/robustness.py`, `eval/user_study/`, `eval/plots.py`, `eval/stats.py` and `eval/report_tables.py`, with their tests. They only read the agent and never change it. The perfect solver (negamax with alpha-beta, bitboards, a transposition table and pruning of losing moves, following Pons [2]) is used for testing only, never inside the agent; it was checked against a plain brute-force search on late-game positions.

## Results against the proposal's targets

| Experiment | Proposal target | Measured | Verdict |
|---|---|---|---|
| Search efficiency (100 positions, depth 8) | >= 10x fewer nodes | 2.35x fewer (tt+ordering vs baseline) | NOT met |
| Playing strength (network vs heuristic, equal-time run) | network wins >= 55% of 200 games | 94W 10D 96L of 200, score 49.5% (95% CI 43%-56%) | NOT met |
| Network vs perfect solver | >= 80% right side winning | 73.2% on 1848 won/lost positions (95% CI 71%-75%) | NOT met |
| Explanation claims checked by brute force | >= 98% correct | 1622/1622 (100.0%) on 500 positions | met |
| Rating study (agent vs score-only) | agent rated higher | NOT RUN YET | - |
| Robustness (heuristic agent) | >= 95% sensible, < 2 s | 120/120 sensible, slowest 1.02s | met |
| Robustness (network agent) | >= 95% sensible, < 2 s | 120/120 sensible, slowest 1.02s | met |

## Playing strength

Network evaluator against the hand-written evaluator, 200 games per run, 1 s per move, 100 random openings of 2 to 8 plies each played twice with the colours swapped. Draws count half. The first two runs were played before a bug in the search clock was fixed: the clock was checked only every 1024 nodes, so the network, which is slower per node, overran its 1 s per move (1.3 to 1.7 s) while the heuristic stayed at 1 s. The run after the fix (checks every 64 nodes) is the only equal-time comparison and is the one used for the verdict. All three are reported.

| Run | W-D-L (network) | Network score | 95% CI (Wilson) | Workers | 55% target |
|---|---|---|---|---|---|
| After the clock fix (equal time) | 94-10-96 | 49.5% | 43%-56% | 3 | NOT met |
| Before the fix, run 1 | 94-11-95 | 49.8% | 43%-57% | 3 | NOT met |
| Before the fix, run 2 (6 workers) | 102-5-93 | 52.2% | 45%-59% | 6 | NOT met |

None of the runs reached the 55% target. Within the intervals the network is not distinguishable from the hand-written evaluator at equal time per move.

## Agreement with the perfect solver

2000 positions of 14 to 30 stones (seed 12345), labelled win/draw/loss by the solver; 570004 position keys (every training position and its mirror image) were excluded, so no test position was seen in training. Solver labels: {'1': 1103, '0': 152, '-1': 745}.

| Evaluator | Right side winning (won/lost positions) | 95% CI | Three-class (draw band) |
|---|---|---|---|
| network | 73.2% | 71%-75% | 65.8% |
| heuristic | 68.2% | 66%-70% | 32.4% |

The headline figure is the first accuracy column. The three-class column treats a score with absolute value up to 100 as a predicted draw; that band suits the network's scale and not the hand-written evaluator's, so the heuristic's three-class figure is not a fair measure and should not be quoted.

## Limitations

* The solver positions come from a sampler (random and shallow-search moves), not from real human games, so the accuracy applies to that mix.
* Match results depend on the machine: search is time-limited, so a slower or busier machine weakens both players. Parallel workers were limited to leave a core free.
* The claim checker confirms that the stated facts are true, not that an explanation is helpful; usefulness is what the rating study measures, with a small number of raters.
* The rating study used 30 randomly sampled mid-game positions (8 to 28 stones). Only positions where the agent's explanation differed from the score-only sentence were used (100% of the sampled positions qualified).

## How to reproduce

See `docs/EVAL.md` for the exact commands.
