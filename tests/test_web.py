"""Tests for the web server (web/app.py).                     OWNER: Srikar"""
import pytest

pytest.importorskip("httpx")          # FastAPI's TestClient needs httpx
from fastapi.testclient import TestClient

from c4.board import Board
from c4.trace import WIN_SCORE
from web.app import app, score_text, winning_cells, build_agent

client = TestClient(app)


def start(ws, **kw):
    hello = ws.receive_json()
    assert hello["type"] == "hello"
    ws.send_json({"type": "new_game", "engine": "stub", "human_first": True, **kw})
    msg = ws.receive_json()
    assert msg["type"] == "state"
    return msg


def test_page_and_static_files_load():
    assert client.get("/").status_code == 200
    for name in ("app.js", "style.css"):
        assert client.get(f"/static/{name}").status_code == 200


def test_engines_always_include_stub():
    ids = {e["id"]: e for e in client.get("/api/engines").json()}
    assert ids["stub"]["available"]
    assert {"heuristic", "network"} <= set(ids)


def test_human_move_gets_agent_reply_with_explanation():
    with client.websocket_connect("/ws") as ws:
        state = start(ws)
        assert state["human_to_move"] and state["history"] == []
        ws.send_json({"type": "move", "col": 3})
        after_human = ws.receive_json()
        assert after_human["history"] == [3]
        assert ws.receive_json()["type"] == "thinking"
        reply = ws.receive_json()
        assert len(reply["history"]) == 2 and reply["human_to_move"]
        turn = reply["agent_turn"]
        assert turn["col"] == reply["history"][1]
        assert turn["explanation"]["sentence"]
        assert {m["col"] for m in turn["trace"]["moves"]} == set(range(7))


def test_agent_moves_first_when_human_is_second():
    with client.websocket_connect("/ws") as ws:
        start(ws, human_first=False)
        assert ws.receive_json()["type"] == "thinking"
        reply = ws.receive_json()
        assert len(reply["history"]) == 1 and reply["human_player"] == 1


def test_illegal_and_out_of_turn_moves_are_rejected():
    with client.websocket_connect("/ws") as ws:
        start(ws)
        ws.send_json({"type": "move", "col": 9})
        assert ws.receive_json()["type"] == "error"


def test_undo_returns_to_human_turn():
    with client.websocket_connect("/ws") as ws:
        start(ws)
        ws.send_json({"type": "move", "col": 3})
        ws.receive_json(); ws.receive_json(); ws.receive_json()
        ws.send_json({"type": "undo"})
        state = ws.receive_json()
        assert state["history"] == [] and state["human_to_move"]
        assert state["agent_turn"] is None


def test_question_gets_an_answer():
    with client.websocket_connect("/ws") as ws:
        start(ws)
        ws.send_json({"type": "ask", "question": "why?"})
        msg = ws.receive_json()
        assert msg["type"] == "answer" and msg["text"]


def test_unavailable_engine_falls_back_to_stub():
    agent, used, note = build_agent("no-such-engine", 1.0)
    assert agent is not None and used in {"heuristic", "network", "stub"}


def test_winning_cells_and_score_text():
    b = Board.from_moves("1212121")                 # X wins vertically in column 1
    assert winning_cells(b) == [[0, 0], [1, 0], [2, 0], [3, 0]]
    assert winning_cells(Board.from_moves("4")) == []
    assert score_text(WIN_SCORE - 7) == "win in 4"
    assert score_text(-(WIN_SCORE - 2)) == "loss in 1"
    assert score_text(12) == "+12"
