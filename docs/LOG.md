# Progress log

One line per piece of work: date, who, what. Everyone adds their own lines.

- 2026-11-16 Rujuta Deshmukh: heuristic evaluator, depth-preferred transposition table, move-ordering verification, node-count comparison script and module/integration tests merged; personally ran the updated-main suite (68 passed, 2 skipped).
- 2026-11-17 Rujuta Deshmukh (with Codex): added reproducible seeded experiment positions, direct UTF-8 CSV output, independent position workers, equal-depth summary and plot helpers, and report draft; focused tests: 27 passed. Full-suite attempt before the summary/parallel tests: 144 passed, 5 skipped, 1 failure because torch is absent in this environment (self-play network test); no teammate code files changed.
- 2026-11-17 Rujuta Deshmukh (with Codex): completed the 100-position depth-8 node-count experiment (400 runs): 82 positions reached depth 8 in all configurations, 18 were solved earlier, none timed out, and scores agreed. Both hooks reduced aggregate depth-8 nodes from 5,934,640 to 2,526,749 (2.35x; 10x target not met). Saved CSV, JSON summary, PNG plot and interpretation in results/, and completed docs/report/rujuta.md.

- 2026-11-16 Mani: perfect solver for testing (eval/solver.py, checked against brute force), 200-game match harness (eval/match.py), solver-agreement check (eval/solver_agreement.py), robustness check (eval/robustness.py), rating-study builder and analysis (eval/user_study/), plots (eval/plots.py), tests for all of them.
- 2026-11-16 Naman: board facts (69 lines, playable and threat cells, odd/even rows), explanation rules with forward chaining (win, block, threat, fork, trap, setup, centre, sacrifice), concept hierarchy, explain_move with saliency fallback for quiet network moves, brute-force claim checker (eval/claim_check.py), tests.
- 2026-11-16 Aditya Kumar Somani (with Claude): sentence templates (c4/explain/templates.py), question parser (c4/qa/parser.py) and answers for the four question types (c4/qa/answers.py) with tests, merged as PR #10 after two rounds of Naman's review; played a game through web/app.py and asked all four questions.
- 2026-11-17 Aditya Kumar Somani (with Claude): final robustness check on main bb1e546: 120/120 sensible, all under 2 s, with the heuristic (slowest 1.01 s) and the round 1 network (slowest 1.07 s); flagged to Srikar that web/app.py does not set game.agent, so what-if searches use the heuristic in network games.
- 2026-11-17 Aditya Kumar Somani (with Claude): QA report draft (docs/report/aditya.md); AI-usage row.

- 2026-11-16: verified 30 unit tests pass; attach game.agent in robustness builder.
