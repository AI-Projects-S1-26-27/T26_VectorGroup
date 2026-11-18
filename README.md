# Glass Box: an explainable Connect-4 agent

**CS F407 Artificial Intelligence, BITS Pilani Hyderabad Campus, First Semester 2026-27**
Instructor-in-charge: Jayati Deshmukh

| | |
| --- | --- |
| Team | 26, **Vector Group** |
| Project | A Connect-4 Agent That Explains Its Own Moves ("Glass Box") |
| Track | Demo |
| Topic areas | Agents and Game Theory (adversarial search), Deep Learning (value network), with Knowledge Representation in a supporting role |

## What it does

A Connect-4 agent that plays using negamax with alpha-beta search and explains
each move in plain English, for example "I played column 4 because it blocks your
three-in-a-row". The explanation is built from the search results and the rules
that actually fired, so the agent only gives reasons it really had. While playing,
you can ask four kinds of question: why a move was played, why not another column,
what would happen after a given column, and who is winning.

The evaluation at the search horizon is either a hand-written heuristic or a small
convolutional network trained on self-play. A browser interface shows the board,
the explanation, column scores and search statistics.

## Team and work division

| Member | ID | Part |
| --- | --- | --- |
| Shridali Singh | 2023B5A70773H | Board, win detection, negamax with alpha-beta, iterative deepening |
| Rujuta Deshmukh | 2023B5A70952H | Move ordering, transposition table, heuristic evaluator, search-efficiency experiments, optional native search |
| Naman Jain | 2024A7PS0132H | Board facts, explanation rules, concept categories, claim checking |
| Aditya Kumar Somani | 2024A7PS0155H | Sentence templates, question matching, "why not" and "what if" answers, robustness check |
| Veer Parekh | 2024A3PS0430H | Self-play pipeline and dataset generation |
| Sriyanth Varma M | 2024A7PS0017H | Network design, training, search integration, saliency |
| CH J Srikar | 2024A1PS0928H | Web interface and demo video |
| Mani Vardhan | 2024A7PS0042H | Perfect solver, match and agreement checks, rating study, plots, report assembly |

Per-member write-ups are in `docs/report/`, the AI-usage disclosure in
`docs/AI_USAGE.md`, the progress log in `docs/LOG.md`.

## Setup

Python 3.10 or newer.

```bash
python -m venv .venv
```

Activate the virtual environment, then install:
- Windows: `.venv\Scripts\activate`
- Windows (Git Bash): `source .venv/Scripts/activate`
- Mac/Linux: `source .venv/bin/activate`

```bash
pip install -r requirements.txt
pytest -q
```

## Run the demo

```bash
python -m uvicorn web.app:app
```

Then open http://127.0.0.1:8000 in a browser. Choose the engine (heuristic or
network), who moves first and the thinking time, then play by clicking a column or
pressing 1 to 7. Use the buttons under the board to ask why, why not, what if and
who is winning.

- `torch` must be installed (it is in `requirements.txt`); the page does not load without it.
- The **heuristic** engine needs nothing else.
- The **network** engine needs trained weights at `models/nn_latest.pt`. Weights are
  not committed. Without them the network engine is shown as not ready and the
  heuristic engine still works. See `docs/report/sriyanth.md` for how the weights
  are trained.
- The optional compiled C++ search (`c4/native_search.cpp`) is off by default and
  needs a C++ compiler; the Python search is the default and the fallback.

## Evaluation

Every experiment in the report has a command, listed in `docs/EVAL.md`. Raw
results are in `results/`, plots in `results/plots/`.

Summary of what was measured against the proposal targets (details and
explanations in the report):

| Target | Result |
| --- | --- |
| Explanation claims at least 98% correct | Met: 1,622 of 1,622 on 500 positions |
| Robustness, at least 95% sensible, under 2 s | Met: 120 of 120, slowest 1.02 s |
| At least 10x fewer nodes than plain minimax at depth 8 | Met: 102.85x on 100 positions |
| Search depth of 10 plies at 1 s | Not met in Python (7 to 9 plies); met only by the optional native search |
| Network wins at least 55% of 200 games | Not met: score 0.495 |
| Network agrees with solver on at least 80% | Not met: 73.2% (heuristic 68.2%) |
| Rating study | Smaller than planned: 18 raters, 6 explanations, mean 4.23 of 5, no score-only baseline |

## Folders

- `c4/` the agent (board, search, explanations, question answering, network, self-play)
- `web/` the browser interface
- `eval/` experiments and evaluation scripts
- `tests/` tests, one file per module
- `docs/` progress log, AI-usage disclosure, contributions, report drafts
- `data/`, `models/` generated data and trained weights (not committed)
- `results/` final tables, plots and the rating-study responses used in the report