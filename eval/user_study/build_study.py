"""Build the explanation rating study.                                 OWNER: Mani

Proposal 4.5: ask 10 to 15 people to rate 30 explanations from 1 to 5 for correctness,
clarity and usefulness, and compare them with a baseline that only reports the score.

Design (within-subject, counterbalanced)
  * 30 positions from the middle of games, each with the agent's real move.
  * Every position has two texts: the agent's explanation (rule layer) and the
    score-only baseline (c4.agent.score_only_explanation).
  * Two question sheets, A and B. Sheet A shows the agent's explanation for odd item
    numbers and the baseline for even ones; sheet B is the opposite. Give raters sheet A
    and B alternately, so every explanation is rated by about half of the raters and
    nobody sees both texts for one position. Raters are not told which text is which.

Run (after Naman's and Aditya's explanation files are on main):
  python -m eval.user_study.build_study --items 30 --seed 7
Creates in results/user_study/:
  items.csv          everything about each item (position, both texts, the key)
  sheet_A.md, sheet_B.md   text to paste into two Google Forms (board drawn with emoji)
  key.json           item -> condition for each sheet (needed by analyse_ratings.py)
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from c4.agent import Agent, score_only_explanation
from c4.board import Board
from c4.game import GameState
from eval.match import Player
from eval.solver_agreement import sample_positions

EMOJI = {1: "🔴", -1: "🟡", 0: "⚪"}


def board_emoji(board: Board) -> str:
    """Board as emoji rows, top row first, absolute colours: red moves first."""
    arr = board.to_absolute()
    rows = ["".join(EMOJI[int(arr[r, c])] for c in range(7)) for r in reversed(range(6))]
    return "\n".join(rows + ["1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣"])


def build_items(n: int, seed: int, evaluator: Player, time_limit: float,
                min_ply: int = 8, max_ply: int = 28, require_explanations: bool = True) -> list[dict]:
    agent = Agent(evaluator.evaluator, time_limit=time_limit, tt=evaluator.tt,
                  order_fn=evaluator.order_fn)
    items = []
    for moves in sample_positions(n, seed, min_ply, max_ply):
        game = GameState(board=Board.from_moves(moves), history=[int(c) - 1 for c in moves])
        result = agent.play_turn(game)
        base = score_only_explanation(result.trace)
        items.append(dict(
            item=len(items) + 1, moves=moves, ply=game.board.num_moves,
            player_to_move="red" if game.board.num_moves % 2 == 0 else "yellow",
            chosen_col=result.col + 1, board=board_emoji(game.board),
            agent_text=result.explanation.sentence, baseline_text=base.sentence,
            concepts=";".join(result.explanation.concepts)))
    if require_explanations and all(i["agent_text"] == i["baseline_text"] for i in items):
        raise SystemExit("The agent's explanations are identical to the score-only baseline: "
                         "the explanation layer (c4/explain/) is not on this branch yet. "
                         "Pull main after Naman and Aditya have merged, then run again.")
    return items


def condition(item_no: int, sheet: str) -> str:
    """'agent' or 'baseline' for this item on this sheet."""
    agent_on_odd = sheet == "A"
    return "agent" if (item_no % 2 == 1) == agent_on_odd else "baseline"


def sheet_markdown(items: list[dict], sheet: str) -> str:
    out = [f"# Rate the explanations (sheet {sheet})", "",
           "In each case a Connect-4 program (yellow or red, shown below as the player to "
           "move) chose a column and gave a reason. Rate the reason from 1 (very bad) to "
           "5 (very good) on three things: **correctness** (is what it says true on this "
           "board?), **clarity** (is it easy to understand?), **usefulness** (does it help "
           "you understand the move?).", ""]
    for it in items:
        text = it["agent_text"] if condition(it["item"], sheet) == "agent" else it["baseline_text"]
        out += [f"## Item {it['item']}", f"Player to move: **{it['player_to_move']}**. "
                f"Red moves first. Columns are numbered 1-7 from the left.", "",
                it["board"], "", f"Program's move and reason: *{text}*", "",
                "Questions (1-5): Correctness / Clarity / Usefulness", ""]
    return "\n".join(out)


def save(items: list[dict], out_dir: str) -> None:
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "items.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(items[0]))
        w.writeheader()
        w.writerows(items)
    for sheet in "AB":
        (d / f"sheet_{sheet}.md").write_text(sheet_markdown(items, sheet), encoding="utf-8")
    key = {s: {str(i["item"]): condition(i["item"], s) for i in items} for s in "AB"}
    (d / "key.json").write_text(json.dumps(key, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--items", type=int, default=30)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--evaluator", default="heuristic")
    p.add_argument("--model", default=None)
    p.add_argument("--time-limit", type=float, default=1.0)
    p.add_argument("--out", default="results/user_study")
    a = p.parse_args(argv)
    items = build_items(a.items, a.seed, Player(a.evaluator, a.model), a.time_limit)
    save(items, a.out)
    print(f"wrote {len(items)} items to {a.out}/ (sheet_A.md, sheet_B.md, key.json, items.csv)")


if __name__ == "__main__":
    main()
