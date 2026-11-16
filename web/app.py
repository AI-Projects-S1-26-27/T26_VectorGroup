"""Browser interface: FastAPI server + one WebSocket per player.   OWNER: Srikar

Run it from the repo root:
    uvicorn web.app:app --reload          (then open http://127.0.0.1:8000)
or  python -m web.app

What this file does
  * serves the page in web/static/ (index.html, app.js, style.css)
  * keeps one GameState (c4/game.py) per open browser tab
  * asks the agent for its move, sends back the board, the explanation and the
    search numbers (depth, nodes, per-column scores, expected line)
  * passes typed questions to the question-answering layer (Aditya, c4/qa/)

It only READS other people's code and never changes it. Parts that are not on
main yet are looked up when needed (same idea as c4/agent.py), so the page works
today on the stub and switches to the real parts automatically once they merge:
    c4.eval_heuristic.HeuristicEvaluator   (Rujuta)   -> "heuristic" engine
    c4.tt.TranspositionTable, c4.ordering.move_ordering (Rujuta)  -> used if present
    c4.nn.evaluator.NNEvaluator            (Sriyanth) -> "network" engine
    c4.qa.answers.answer(question, game) -> str   (Aditya) -> question box

WebSocket protocol  (/ws, JSON messages)
  browser -> server
    {"type": "new_game", "engine": "heuristic"|"network"|"stub",
                         "human_first": true, "time_limit": 1.0}
    {"type": "move", "col": 0-6}
    {"type": "undo"}                      take back your last move (and the reply)
    {"type": "ask", "question": "why not column 5?"}
  server -> browser
    {"type": "hello", "engines": [{"id", "label", "available", "why"}]}
    {"type": "state", ...}               after every change, see state_message()
    {"type": "thinking"}                 the agent has started searching
    {"type": "answer", "question", "text"}
    {"type": "error", "text"}
Columns are 0-6 on the wire and 1-7 on screen. Board rows: row 0 = bottom.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from c4.agent import Agent
from c4.board import Board, HEIGHT, WIDTH
from c4.game import GameState, TurnResult
from c4.stub_agent import StubAgent
from c4.trace import SearchTrace, is_decided, own_moves_to_win, plies_to_end

log = logging.getLogger("web")
STATIC = Path(__file__).parent / "static"
MIN_TIME, MAX_TIME, DEFAULT_TIME = 0.1, 10.0, 1.0


# ------------------------------------------------------------ optional parts
def _optional(module_name: str, attr: str):
    """module.attr, or None if that file/function is not on main yet.
    A real bug inside the module is NOT hidden."""
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as err:
        if err.name == module_name:
            return None
        raise
    return getattr(module, attr, None)


ENGINES = {                      # id -> (label, module, class)
    "heuristic": ("Search + heuristic", "c4.eval_heuristic", "HeuristicEvaluator"),
    "network": ("Search + neural network", "c4.nn.evaluator", "NNEvaluator"),
    "stub": ("Stub (random, for testing)", None, None),
}


def _make_evaluator(engine: str):
    """Returns (evaluator or None, reason it is unavailable)."""
    _, module, cls_name = ENGINES[engine]
    cls = _optional(module, cls_name)
    if cls is None:
        return None, f"{module}.{cls_name} is not on main yet"
    try:
        return cls(), ""
    except Exception as err:     # e.g. the network weights are not downloaded
        return None, f"could not start {cls_name}: {err}"


@lru_cache(maxsize=1)           # checked once per server start (restart after a merge)
def engine_list() -> list[dict]:
    out = []
    for eid, (label, _, _) in ENGINES.items():
        if eid == "stub":
            ok, why = True, ""
        else:
            ev, why = _make_evaluator(eid)
            ok = ev is not None
        out.append({"id": eid, "label": label, "available": ok, "why": why})
    return out


def default_engine() -> str:
    return next(e["id"] for e in engine_list() if e["available"])


def build_agent(engine: str, time_limit: float):
    """Returns (agent, engine actually used, note for the user or "")."""
    if engine not in ENGINES:
        engine = default_engine()
    if engine == "stub":
        return StubAgent(), "stub", ""
    evaluator, why = _make_evaluator(engine)
    if evaluator is None:
        return StubAgent(), "stub", f"{ENGINES[engine][0]} is not available ({why}), using the stub."
    tt_cls = _optional("c4.tt", "TranspositionTable")
    order_fn = _optional("c4.ordering", "move_ordering")
    agent = Agent(evaluator, time_limit=time_limit,
                  tt=tt_cls() if tt_cls else None, order_fn=order_fn)
    return agent, engine, ""


# ------------------------------------------------------------- JSON helpers
def score_text(score: int) -> str:
    """Score as a person would say it, from the AGENT's point of view."""
    if is_decided(score):
        if score > 0:
            return f"win in {own_moves_to_win(score)}"
        if score < 0:
            return f"loss in {max(1, plies_to_end(score) // 2)}"
    return f"{score:+d}"


def winning_cells(board: Board) -> list[list[int]]:
    """[row, col] of every stone in a finished four-in-a-row (empty if none)."""
    if not board.last_mover_won():
        return []
    arr = board.to_absolute()
    who = 1 if board.num_moves % 2 == 1 else -1      # the player who just moved
    cells = set()
    for r in range(HEIGHT):
        for c in range(WIDTH):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (-1, 1)):
                line = [(r + i * dr, c + i * dc) for i in range(4)]
                if all(0 <= rr < HEIGHT and 0 <= cc < WIDTH and arr[rr][cc] == who
                       for rr, cc in line):
                    cells.update(line)
    return [list(cell) for cell in sorted(cells)]


def _fact(f) -> dict:
    d = asdict(f)
    d["cells"] = [list(cell) for cell in d["cells"]]
    return d


def trace_json(trace: SearchTrace) -> dict:
    return {
        "chosen": trace.chosen,
        "depth": trace.depth,
        "nodes": trace.nodes,
        "time_s": round(trace.time_s, 3),
        "nps": int(trace.nodes / trace.time_s) if trace.time_s > 0 else None,
        "evaluator": trace.evaluator,
        "score": trace.score,
        "score_text": score_text(trace.score),
        "static_score": trace.static_score,
        "moves": [{
            "col": m.col,
            "score": m.score,
            "score_text": score_text(m.score),
            "depth": m.depth,
            "pv": m.pv,
            "facts": [_fact(f) for f in m.facts],
        } for m in sorted(trace.moves.values(), key=lambda m: m.col)],
    }


def turn_json(result: TurnResult) -> dict:
    e = result.explanation
    return {
        "col": result.col,
        "explanation": {
            "sentence": e.sentence,
            "concepts": list(e.concepts),
            "facts": [_fact(f) for f in e.facts],
            "score_before": e.score_before,
            "score_after": e.score_after,
        },
        "trace": trace_json(result.trace),
    }


# ------------------------------------------------------------------ session
class Session:
    """One browser tab = one game."""

    def __init__(self):
        self.engine = "stub"
        self.time_limit = DEFAULT_TIME
        self.agent = StubAgent()
        self.game = GameState()
        self.last_turn: TurnResult | None = None

    @property
    def human_player(self) -> int:
        return 0 if self.game.human_first else 1

    def human_to_move(self) -> bool:
        b = self.game.board
        return not b.is_over() and b.player_to_move == self.human_player

    def new_game(self, engine: str, human_first: bool, time_limit: float) -> str:
        self.time_limit = min(MAX_TIME, max(MIN_TIME, float(time_limit)))
        self.agent, self.engine, note = build_agent(engine, self.time_limit)
        self.game = GameState(human_first=bool(human_first))
        self.last_turn = None
        return note

    def undo(self) -> None:
        """Take moves back until it is the human's turn again (at least one)."""
        history = list(self.game.history)
        if not history:
            return
        history.pop()
        board = Board.from_moves("".join(str(c + 1) for c in history))
        while history and board.player_to_move != self.human_player:
            history.pop()
            board = Board.from_moves("".join(str(c + 1) for c in history))
        self.game = GameState(board=board, history=history,
                              human_first=self.game.human_first)
        self.last_turn = None
        tt = getattr(self.agent, "tt", None)
        if tt is not None and hasattr(tt, "clear"):
            tt.clear()


def state_message(s: Session, agent_turn: TurnResult | None = None) -> dict:
    b = s.game.board
    if b.last_mover_won():
        winner = 1 - b.player_to_move          # 0 = X, 1 = O
        result = "human" if winner == s.human_player else "agent"
    elif b.is_draw():
        result = "draw"
    else:
        result = None
    return {
        "type": "state",
        "board": b.to_absolute().tolist(),     # 6 rows, row 0 = bottom; 1 = X, -1 = O
        "history": list(s.game.history),
        "human_player": s.human_player,
        "to_move": b.player_to_move,
        "human_to_move": s.human_to_move(),
        "legal": b.legal_moves() if not b.is_over() else [],
        "over": b.is_over(),
        "result": result,
        "winning_cells": winning_cells(b),
        "engine": s.engine,
        "time_limit": s.time_limit,
        "agent_turn": turn_json(agent_turn) if agent_turn else None,
    }


# ---------------------------------------------------------------- questions
def answer_question(question: str, game: GameState) -> str:
    """Hand the question to Aditya's layer: c4.qa.answers.answer(question, game)."""
    answer = _optional("c4.qa.answers", "answer")
    if answer is None:
        return "Questions are not connected yet (c4/qa/answers.py is not on main)."
    try:
        reply = answer(question, game)
    except NotImplementedError:
        return "Questions are not connected yet (answers.py is still a stub)."
    return reply if isinstance(reply, str) else str(getattr(reply, "text", reply))


# ------------------------------------------------------------------- server
app = FastAPI(title="Glass Box Connect-4")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/engines")
async def engines():
    return engine_list()


async def agent_move(s: Session, ws: WebSocket) -> None:
    await ws.send_json({"type": "thinking"})
    result = await asyncio.to_thread(s.agent.play_turn, s.game)   # keep the server responsive
    s.game.record_agent_turn(result)
    s.last_turn = result
    await ws.send_json(state_message(s, result))


async def handle(s: Session, msg: dict, ws: WebSocket) -> None:
    kind = msg.get("type")

    if kind == "new_game":
        note = s.new_game(msg.get("engine", default_engine()),
                          msg.get("human_first", True),
                          msg.get("time_limit", DEFAULT_TIME))
        if note:
            await ws.send_json({"type": "error", "text": note})
        await ws.send_json(state_message(s))
        if not s.human_to_move() and not s.game.board.is_over():
            await agent_move(s, ws)

    elif kind == "move":
        col = msg.get("col")
        if not s.human_to_move():
            await ws.send_json({"type": "error", "text": "It is not your turn."})
            return
        if not isinstance(col, int) or col not in s.game.board.legal_moves():
            await ws.send_json({"type": "error", "text": "That column is full or not valid."})
            return
        s.game.apply_move(col)
        await ws.send_json(state_message(s))
        if not s.game.board.is_over():
            await agent_move(s, ws)

    elif kind == "undo":
        s.undo()
        await ws.send_json(state_message(s))

    elif kind == "ask":
        question = str(msg.get("question", "")).strip()[:300]
        if not question:
            return
        text = await asyncio.to_thread(answer_question, question, s.game)
        await ws.send_json({"type": "answer", "question": question, "text": text})

    else:
        await ws.send_json({"type": "error", "text": f"unknown message type {kind!r}"})


@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    s = Session()
    await ws.send_json({"type": "hello", "engines": engine_list(),
                        "default_engine": default_engine()})
    try:
        while True:
            msg = await ws.receive_json()
            try:
                await handle(s, msg, ws)
            except WebSocketDisconnect:
                raise
            except Exception as err:          # a bug in some part: report it, keep the page alive
                log.exception("error while handling %r", msg)
                await ws.send_json({"type": "error",
                                    "text": f"Server error: {type(err).__name__}: {err}"})
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="127.0.0.1", port=8000, reload=True)
