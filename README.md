# Glass Box: an explainable Connect-4 agent

CS F407 Artificial Intelligence, Team 26 (Vector Group), Demo track.

A Connect-4 agent that plays using negamax with alpha-beta search and explains
each move in plain English. Explanations are built from the search results and
rules that actually fired, so the agent only gives reasons it really had.

## Setup

```bash
python -m venv .venv
pip install -r requirements.txt
```

Activate the virtual environment before installing:
- Windows: `.venv\Scripts\activate`
- Windows (Git Bash): `source .venv/Scripts/activate`
- Mac/Linux: `source .venv/bin/activate`

Run the tests with:

```bash
pytest -q
```

## Folders

- `c4/` the agent (board, search, explanations, question answering, network, self-play)
- `web/` the browser interface
- `eval/` experiments and evaluation scripts
- `tests/` tests, one file per module
- `docs/` progress log, AI-usage disclosure, contributions, report drafts
- `data/`, `models/` generated data and trained weights (not committed)
- `results/` final tables and plots used in the report

## Team

Shridali Singh, Rujuta Deshmukh, Naman Jain, Aditya Kumar Somani,
Veer Parekh, Sriyanth Varma M, CH J Srikar, Mani Vardhan