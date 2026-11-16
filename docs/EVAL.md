# Running the experiments (proposal section 4.5)

Run everything from the repo root with the virtual environment active. Results go to
`results/` (commit the small JSON/CSV/PNG files there, never anything in `data/` or `models/`).

| Proposal target | Command | Needs | Output |
|---|---|---|---|
| Learned beats hand-written (>= 55% over 200 games, 1 s per move) | `python -m eval.match --a network --a-model models/nn_latest.pt --b heuristic --games 200 --time-limit 1.0 --workers 3 --out results/match/network_vs_heuristic` | trained network | results/match/*.csv, *.json |
| Search efficiency (>= 10x fewer nodes at depth 8) | `python -m eval.node_counts --depth 8 > results/node_counts.csv` (Rujuta's script; edit its positions to the 100 fixed ones) | nothing | results/node_counts.csv |
| Network agrees with solver (>= 80% on 2,000 unseen positions) | `python -m eval.solver_agreement --positions 2000 --model models/nn_latest.pt --exclude-data data/selfplay/round_1 data/selfplay/round_2 --workers 3` | trained network, self-play data folders | results/solver_agreement/ |
| Explanations are correct (>= 98% of claims) | Naman's `eval/claim_check.py` | explain layer | results/ |
| Rating study (10 to 15 raters, 30 explanations) | `python -m eval.user_study.build_study`, share sheet_A / sheet_B (alternate raters), then `python -m eval.user_study.analyse_ratings ratings.csv` | explain layer | results/user_study/ |
| Robustness (>= 95% sensible, < 2 s) | `python -m eval.robustness` | Aditya's c4/qa/answers.py | results/robustness/ |
| All plots | `python -m eval.plots` | the files above | results/plots/*.png |

Notes
* Use `--workers` at most (CPU cores - 1). Time-limited search gets weaker on a busy machine.
* `eval/solver.py` is a pure-Python perfect solver; it is fine from about 14 stones up. For
  positions with fewer stones build Pascal Pons's solver (github.com/PascalPons/connect4) and set
  `C4_SOLVER_BIN=/path/to/c4solver`; every script then uses it automatically.
* Say in the report that the solver is used only for testing, never inside the agent.
