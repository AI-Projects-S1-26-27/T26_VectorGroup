# Progress log

One line per piece of work: date, who, what. Everyone adds their own lines.

- 2026-11-16 Rujuta Deshmukh: heuristic evaluator, depth-preferred transposition table, move-ordering verification, node-count comparison script and module/integration tests merged; personally ran the updated-main suite (68 passed, 2 skipped).
- 2026-11-17 Rujuta Deshmukh (with Codex): added reproducible seeded experiment positions, direct UTF-8 CSV output, independent position workers, equal-depth summary and plot helpers, and report draft; focused tests: 27 passed. Full-suite attempt before the summary/parallel tests: 144 passed, 5 skipped, 1 failure because torch is absent in this environment (self-play network test); no teammate code files changed.
- 2026-11-17 Rujuta Deshmukh (with Codex): completed the 100-position depth-8 node-count experiment (400 runs): 82 positions reached depth 8 in all configurations, 18 were solved earlier, none timed out, and scores agreed. Both hooks reduced aggregate depth-8 nodes from 5,934,640 to 2,526,749 (2.35x; 10x target not met). Saved CSV, JSON summary, PNG plot and interpretation in results/, and completed docs/report/rujuta.md.

- 2026-11-16 Mani: perfect solver for testing (eval/solver.py, checked against brute force), 200-game match harness (eval/match.py), solver-agreement check (eval/solver_agreement.py), robustness check (eval/robustness.py), rating-study builder and analysis (eval/user_study/), plots (eval/plots.py), tests for all of them.
- 2026-11-16 Naman: board facts (69 lines, playable and threat cells, odd/even rows), explanation rules with forward chaining (win, block, threat, fork, trap, setup, centre, sacrifice), concept hierarchy, explain_move with saliency fallback for quiet network moves, brute-force claim checker (eval/claim_check.py), tests.

- 2026-11-16: verified 30 unit tests pass; attach game.agent in robustness builder.

- 2026-11-16 Veer Parekh (with Claude): self-play generator (c4/selfplay/generate.py) and dataset loader/encoder (c4/selfplay/dataset.py) with 20 tests, merged as PR #5; checked with Rujuta's heuristic, table and ordering (about 4 games/s per CPU core at depth 4).
- 2026-11-16 Veer Parekh (with Claude): reviewed Sriyanth's PR #9 by running generate, train and network self-play end to end (approved); reviewed Naman's PR #6 by running the claim checker on 6,500 positions (approved).
- 2026-11-16 Veer Parekh (with Claude): round 2 self-play with the round 1 network: 5,000 games, 149,181 positions, depth 4, 2 to 8 random opening moves; every game replayed to check legality and labels; data/selfplay/round_2 handed to Sriyanth, who used it for the round 2 network (77.2% winner accuracy vs 75.3%).
- 2026-11-17 Veer Parekh (with Claude): self-play report draft (docs/report/veer.md) with the dataset handoff confirmation; AI-usage row.
