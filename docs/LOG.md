# Progress log

One line per piece of work: date, who, what. Everyone adds their own lines.

- 2026-11-18 Rujuta Deshmukh (with Codex): completed the original 100-position depth-8 comparison (300/300 complete, no node cap, no timeouts). Optional compiled exhaustive minimax matched all 288 saved completed Python minimax runs exactly. Actual nodes: minimax 217,990,090; alpha-beta 4,078,411; optimized 2,119,497. The 102.85x minimax/optimized reduction meets the 10x depth-8 target; extra gain over alpha-beta is 1.92x. All root scores agree; 44 focused tests pass. Runtime comparisons across backends are explicitly excluded. Saved complete CSV/JSON/plot, validation artifact and report update; remaining deep sweep coverage is not claimed complete.

- 2026-11-18 Rujuta Deshmukh (with Codex): after receiving the original proposal, added a separate single-depth minimax/alpha-beta/optimized sweep over the original 100 positions and all depths 4-12, with checkpoint/resume and explicit 20,000-node/10-second per-run limits. All 2,700 attempts are saved: 1,315 complete, 1,360 node-limited, 25 time-limited; completed root scores agree. Full-sample ratios are 3.09x at depth 4 and 7.91x at depth 5. Numerical coverage at depths 6-12 remains incomplete; the full-100-position depth-8 target is not fully measured. Saved CSV, JSON, plot and notes; extended focused suite: 38 passed. No teammate code changed.

- 2026-11-16 Rujuta Deshmukh: heuristic evaluator, depth-preferred transposition table, move-ordering verification, node-count comparison script and module/integration tests merged; personally ran the updated-main suite (68 passed, 2 skipped).
- 2026-11-17 Rujuta Deshmukh (with Codex): added reproducible seeded experiment positions, direct UTF-8 CSV output, independent position workers, equal-depth summary and plot helpers, and report draft; focused tests: 27 passed. Full-suite attempt before the summary/parallel tests: 144 passed, 5 skipped, 1 failure because torch is absent in this environment (self-play network test); no teammate code files changed.
- 2026-11-17 Rujuta Deshmukh (with Codex): completed the 100-position depth-8 node-count experiment (400 runs): 82 positions reached depth 8 in all configurations, 18 were solved earlier, none timed out, and scores agreed. Both hooks reduced aggregate depth-8 nodes from 5,934,640 to 2,526,749 (2.35x; 10x target not met). Saved CSV, JSON summary, PNG plot and interpretation in results/, and completed docs/report/rujuta.md.

- 2026-11-16 Mani: perfect solver for testing (eval/solver.py, checked against brute force), 200-game match harness (eval/match.py), solver-agreement check (eval/solver_agreement.py), robustness check (eval/robustness.py), rating-study builder and analysis (eval/user_study/), plots (eval/plots.py), tests for all of them.
- 2026-11-16 Naman: board facts (69 lines, playable and threat cells, odd/even rows), explanation rules with forward chaining (win, block, threat, fork, trap, setup, centre, sacrifice), concept hierarchy, explain_move with saliency fallback for quiet network moves, brute-force claim checker (eval/claim_check.py), tests.
- 2026-11-16 Aditya Kumar Somani (with Claude): sentence templates (c4/explain/templates.py), question parser (c4/qa/parser.py) and answers for the four question types (c4/qa/answers.py) with tests, merged as PR #10 after two rounds of Naman's review; played a game through web/app.py and asked all four questions.
- 2026-11-17 Aditya Kumar Somani (with Claude): final robustness check on main d889af7: 120/120 sensible, all under 2 s, with the heuristic (slowest 1.02 s) and the round 1 network (slowest 1.16 s), results saved in results/robustness/heuristic and results/robustness/network; flagged to Srikar that web/app.py does not set game.agent, so what-if searches use the heuristic in network games.
- 2026-11-17 Aditya Kumar Somani (with Claude): QA report draft (docs/report/aditya.md); AI-usage row.

- 2026-11-16: verified 30 unit tests pass; attach game.agent in robustness builder.

- 2026-11-16 Veer Parekh (with Claude): self-play generator (c4/selfplay/generate.py) and dataset loader/encoder (c4/selfplay/dataset.py) with 20 tests, merged as PR #5; checked with Rujuta's heuristic, table and ordering (about 4 games/s per CPU core at depth 4).
- 2026-11-16 Veer Parekh (with Claude): reviewed Sriyanth's PR #9 by running generate, train and network self-play end to end (approved); reviewed Naman's PR #6 by running the claim checker on 6,500 positions (approved).
- 2026-11-16 Veer Parekh (with Claude): round 2 self-play with the round 1 network: 5,000 games, 149,181 positions, depth 4, 2 to 8 random opening moves; every game replayed to check legality and labels; data/selfplay/round_2 handed to Sriyanth, who used it for the round 2 network (77.2% winner accuracy vs 75.3%).
- 2026-11-17 Veer Parekh (with Claude): self-play report draft (docs/report/veer.md) with the dataset handoff confirmation; AI-usage row.
- 2026-11-17 Naman Jain (with Claude): saved claim-check result (results/claim_check.json: 500 positions, 1622/1622 claims correct, target met; new --out option in eval/claim_check.py), report draft (docs/report/naman.md), explain_move switched to Aditya's templates; reviewed Aditya's PR #10 twice and PR #16.
- 2026-11-18 Naman Jain (with Claude): updated AI-usage row.

- 2026-11-15 Shridali Singh (with Claude): repo structure, board and bitboard win detection, trace format, evaluator interface, game state and stub agent, with tests; merged as PR #1.
- 2026-11-15 Shridali Singh (with Claude): negamax with alpha-beta, iterative deepening and the table/ordering hooks (c4/search.py) and the agent (c4/agent.py), with tests.
- 2026-11-16 Shridali Singh: merged Srikar's PR #7 and updated main.
- 2026-11-18 Shridali Singh (with Claude): updated requirements.txt (added httpx; 174 tests passed); measured search depth (eval/measure_search.py); ran the 200-game network vs heuristic match (94-10-96, score 0.495, target not met); found and fixed a time-check bug (clock checked every 1024 nodes, network overran 1 s), and saved both match runs in results/match/.
- 2026-11-18 Shridali Singh (with Claude): added eval/ordering_experiments.py, a separate experiment (not used by the agent) comparing an exact key with a Zobrist-style key, and with and without killer moves, at depth 8 on the 100 seeded positions. Same root scores in all configurations. Zobrist key: identical nodes (2,526,749), no collisions in 855,191 keys, slower per key. Killer moves: 2,291,782 nodes (9.3% fewer) but about 7% more time in Python. Neither adopted; results in results/ordering_experiments*.

- 2026-11-16 CH J Srikar (with Claude): web interface (web/app.py, web/static/): FastAPI + WebSocket server, board, explanation panel, stats toggles and question box, with 9 tests; merged as PR #7.
- 2026-11-18 CH J Srikar (with Claude): set game.agent in web/app.py so what-if and who-is-winning use the game's engine (flagged by Aditya).
- 2026-11-18 CH J Srikar: set up the demo on my laptop with the round 2 network; demo video recorded with Claude; AI-usage row.
