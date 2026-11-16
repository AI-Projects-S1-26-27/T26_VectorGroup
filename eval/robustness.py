"""Robustness check for the question box.                          OWNER: Mani

Proposal 4.5: build a set of over 100 unusual or badly formed questions and check that
at least 95% get a sensible reply, with answers coming back in under two seconds.

Calls Aditya's  c4.qa.answers.answer(question, game) -> str  on every question, each in
one of four game situations (see STATES). A reply is SENSIBLE when
  * nothing crashes and the reply is a non-empty plain string (no traceback text),
  * it is short (<= MAX_CHARS),
  * it matches what the question deserves:
      expect "answer"    a real answer (NOT the generic "you can ask ..." reply)
      expect "fallback"  the short reply that lists what can be asked
      expect "either"    anything sensible (ambiguous input)
  * it arrives in under TIME_LIMIT seconds.
A reply counts as the fallback when it mentions at least FALLBACK_MIN of FALLBACK_MARKERS
(the fallback lists the four question types). If Aditya's wording differs, change the
markers below or pass --fallback-markers.

Usage (repo root, after c4/qa/answers.py is on main):
  python -m eval.robustness                    # real agent, heuristic evaluator
  python -m eval.robustness --evaluator network --model models/nn_latest.pt
Writes results/robustness/robustness.csv and .json
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import time
from pathlib import Path

from c4.board import Board
from c4.game import GameState

TARGET_RATE = 0.95
TIME_LIMIT = 2.0
MAX_CHARS = 600
FALLBACK_MARKERS = ("why did you", "why not", "what if", "who is winning", "who's winning")
FALLBACK_MIN = 3

# game situations: a move string for the position, who has moved
STATES = {
    "mid": "44",            # human played the centre, agent replied (set up by build_game)
    "start": "",            # nothing played yet, no agent move to talk about
    "full_column": "4444441",   # column 4 is full (6 stones)
    "over": "1212121",      # human wins vertically in column 1 -> game finished
}


def build_game(state: str, agent) -> GameState:
    """Make a GameState in the named situation; the agent has answered the human's last
    move whenever the position allows it."""
    game = GameState()
    game.agent = agent
    if state == "start":
        return game
    moves = STATES[state]
    if state == "mid":
        game.apply_move(3)
        game.record_agent_turn(agent.play_turn(game))
        return game
    for ch in moves:
        game.apply_move(int(ch) - 1)
    if not game.board.is_over() and game.board.num_moves % 2 == 1:
        game.record_agent_turn(agent.play_turn(game))
    return game


# --------------------------------------------------------------- the questions
def build_questions() -> list[tuple[str, str, str, str]]:
    """(question, category, expect, state) -- over 100 of them."""
    q: list[tuple[str, str, str, str]] = []

    def add(items, state="mid"):
        q.extend((text, cat, exp, state) for text, cat, exp in items)

    # --- the four supported types, ordinary and paraphrased
    add([("Why did you play there?", "why", "answer"), ("why that move", "why", "answer"),
         ("Why did you play that?", "why", "answer"), ("explain your move", "why", "answer"),
         ("why column 4", "why", "either"), ("What was your reasoning?", "why", "answer"),
         ("why not column 5?", "why_not", "answer"), ("Why not col 2?", "why_not", "answer"),
         ("why didn't you play column 6", "why_not", "answer"),
         ("why not the left one", "why_not", "either"),
         ("what if I play column 3?", "what_if", "answer"), ("what if i play col 7", "what_if", "answer"),
         ("What happens if I go in column 1?", "what_if", "answer"),
         ("and if I play 4?", "what_if", "either"),
         ("who is winning?", "winning", "answer"), ("Who's winning", "winning", "answer"),
         ("who is ahead", "winning", "answer"), ("am I winning?", "winning", "answer"),
         ("can you win?", "winning", "either"), ("what's the score", "winning", "either")])
    # --- column spellings
    for text in ("why not column five", "why not col 5", "why not column 5", "why not c5",
                 "why not the 5th column", "why not fifth column", "why not the middle one",
                 "why not the middle column", "why not the first column", "why not the last column",
                 "why not the rightmost one", "why not the leftmost column", "why not  column   5  ",
                 "WHY NOT COLUMN FIVE?!", "why not COL5", "what if I play the middle one?",
                 "what if I play column seven", "what if I play the 2nd column"):
        add([(text, "column_spelling", "answer")])
    # --- invalid columns and numbers
    for text in ("why not column 0", "why not column 8", "why not column 99", "why not column -1",
                 "what if I play column 0", "what if I play column 8", "why not column three point five",
                 "why not column 5 and 6"):
        add([(text, "bad_column", "either")])
    # --- typos, case, punctuation, spacing
    for text in ("wyh did you play there", "why did u play thre", "WHY DID YOU PLAY THERE",
                 "why did you play there????", "...why did you play there", "why   did   you   play   there",
                 "why did you play there\n", "\twho is winning", "whoo is winning", "why nott column 5",
                 "wat if i play col 3", "Why did you play there? Thanks!", "pls tell me who is winning"):
        add([(text, "typo_format", "either")])
    # --- off topic and out of scope
    for text in ("hello", "hi there", "what is the weather today", "tell me a joke",
                 "who are you", "what is the capital of France", "can you play chess",
                 "write me a poem", "how do I win at Connect 4 in general", "what is your name",
                 "thanks", "ok", "lol", "i give up", "undo my move", "restart the game",
                 "what is the meaning of life", "explain minimax", "what is your evaluation function",
                 "which move should I play?", "give me a hint"):
        add([(text, "off_topic", "fallback")])
    # --- degenerate input
    for text in ("", " ", "   \n\t  ", "?", "???", "!!!", "1", "5", "column 5", ".", "why", "what if",
                 "why not", "who", "a" * 5000, "why did you play there? " * 100,
                 "😀", "why did you play there 😀", "为什么这样走", "pourquoi pas la colonne 5",
                 "<script>alert(1)</script>", "'; DROP TABLE games;--", "{{7*7}}", "%s%s%s%s",
                 "why not column 5\x00", "null", "None", "undefined"):
        add([(text, "degenerate", "either")])
    # --- several questions in one message
    for text in ("why did you play there and who is winning", "why not column 5 and what if I play 3",
                 "who is winning? why did you play there?"):
        add([(text, "multi", "either")])
    # --- situations where the question cannot be answered
    for text, exp in (("why did you play there?", "fallback"), ("why not column 5?", "fallback"),
                      ("who is winning?", "either")):
        add([(text, "no_agent_move_yet", exp)], state="start")
    for text in ("what if I play column 4?", "why not column 4?", "what if I play column 4 again"):
        add([(text, "full_column", "fallback")], state="full_column")
    for text in ("why did you play there?", "what if I play column 3?", "who is winning?"):
        add([(text, "game_over", "fallback")], state="over")
    return q


# ------------------------------------------------------------------ checking
def is_fallback(text: str, markers=FALLBACK_MARKERS, minimum=FALLBACK_MIN) -> bool:
    low = text.lower()
    return sum(m in low for m in markers) >= minimum


def judge(reply, expect: str, elapsed: float, markers=FALLBACK_MARKERS, minimum=FALLBACK_MIN):
    """Return (sensible: bool, reason: str)."""
    if not isinstance(reply, str) or not reply.strip():
        return False, "empty or non-string reply"
    if "Traceback" in reply or "Error:" in reply or "Exception" in reply:
        return False, "error text in reply"
    if len(reply) > MAX_CHARS:
        return False, f"reply longer than {MAX_CHARS} characters"
    if elapsed >= TIME_LIMIT:
        return False, f"too slow ({elapsed:.2f}s)"
    fb = is_fallback(reply, markers, minimum)
    if expect == "answer" and fb:
        return False, "gave the generic fallback to a valid question"
    if expect == "fallback" and not fb:
        return False, "did not list what can be asked"
    return True, "ok"


def run_check(answer_fn, make_game, questions=None, markers=FALLBACK_MARKERS,
              minimum=FALLBACK_MIN) -> dict:
    """Run every question. answer_fn(question, game) -> str; make_game(state) -> GameState."""
    questions = questions or build_questions()
    cache: dict[str, GameState] = {}
    rows = []
    for question, cat, expect, state in questions:
        game = cache.get(state) or cache.setdefault(state, make_game(state))
        t0 = time.perf_counter()
        try:
            reply = answer_fn(question, game)
            err = ""
        except Exception as e:                      # a crash is a failed question
            reply, err = None, f"{type(e).__name__}: {e}"
        elapsed = time.perf_counter() - t0
        ok, reason = judge(reply, expect, elapsed, markers, minimum)
        if err:
            ok, reason = False, "crashed: " + err
        rows.append(dict(question=question[:80].replace("\n", "\\n"), category=cat,
                         state=state, expect=expect, sensible=int(ok), reason=reason,
                         seconds=round(elapsed, 3),
                         reply=(reply or "")[:200].replace("\n", " ")))
    n = len(rows)
    sensible = sum(r["sensible"] for r in rows)
    times = sorted(r["seconds"] for r in rows)
    cats: dict[str, list[int]] = {}
    for r in rows:
        cats.setdefault(r["category"], []).append(r["sensible"])
    summary = dict(questions=n, sensible=sensible, sensible_rate=sensible / n,
                   target=TARGET_RATE, target_met=bool(sensible / n >= TARGET_RATE),
                   under_2s_rate=sum(t < TIME_LIMIT for t in times) / n,
                   median_seconds=times[n // 2], p95_seconds=times[int(0.95 * (n - 1))],
                   max_seconds=times[-1],
                   by_category={c: f"{sum(v)}/{len(v)}" for c, v in cats.items()},
                   failures=[r for r in rows if not r["sensible"]])
    return {"rows": rows, "summary": summary}


def save(result: dict, out_dir: str) -> None:
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    rows = result["rows"]
    with open(d / "robustness.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (d / "robustness.json").write_text(json.dumps(result["summary"], indent=2, ensure_ascii=False),
                                       encoding="utf-8")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--evaluator", default="heuristic")
    p.add_argument("--model", default=None)
    p.add_argument("--time-limit", type=float, default=1.0, help="agent seconds per move")
    p.add_argument("--fallback-markers", nargs="+", default=list(FALLBACK_MARKERS))
    p.add_argument("--fallback-min", type=int, default=FALLBACK_MIN)
    p.add_argument("--out", default="results/robustness")
    a = p.parse_args(argv)
    try:
        answer_fn = importlib.import_module("c4.qa.answers").answer
    except ModuleNotFoundError as err:
        if err.name in ("c4.qa.answers", "c4.qa"):
            raise SystemExit("c4/qa/answers.py is not on this branch yet: pull main after "
                             "Aditya has merged it.")
        raise
    from c4.agent import Agent
    from eval.match import Player
    agent = Agent(Player(a.evaluator, a.model).evaluator, time_limit=a.time_limit)
    result = run_check(answer_fn, lambda s: build_game(s, agent), None,
                       tuple(m.lower() for m in a.fallback_markers), a.fallback_min)
    save(result, a.out)
    s = result["summary"]
    print(json.dumps({k: s[k] for k in ("questions", "sensible", "sensible_rate", "target_met",
                                        "under_2s_rate", "p95_seconds", "max_seconds",
                                        "by_category")}, indent=2))
    for f in s["failures"][:15]:
        print("FAIL:", f["category"], repr(f["question"]), "->", f["reason"])


if __name__ == "__main__":
    main()
