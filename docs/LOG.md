# Progress log

One line per piece of work: date, who, what. Everyone adds their own lines.

- 2026-11-16 Mani: perfect solver for testing (eval/solver.py, checked against brute force), 200-game match harness (eval/match.py), solver-agreement check (eval/solver_agreement.py), robustness check (eval/robustness.py), rating-study builder and analysis (eval/user_study/), plots (eval/plots.py), tests for all of them.
- 2026-11-16 Naman: board facts (69 lines, playable and threat cells, odd/even rows), explanation rules with forward chaining (win, block, threat, fork, trap, setup, centre, sacrifice), concept hierarchy, explain_move with saliency fallback for quiet network moves, brute-force claim checker (eval/claim_check.py), tests.
