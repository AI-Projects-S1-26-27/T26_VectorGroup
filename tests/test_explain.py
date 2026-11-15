"""Tests for c4/explain (facts, concepts, rules, explain) and eval/claim_check."""
import numpy as np

from c4.agent import Agent
from c4.board import Board
from c4.explain.concepts import ancestors, is_a, rank
from c4.explain.explain import explain_move
from c4.explain.facts import LINES, is_odd_row, playable_cells, threat_cells
from c4.explain.rules import detect_facts, forward_chain, move_context
from c4.search import search
from c4.trace import MoveInfo, SearchTrace
from eval.claim_check import run

X, O = 1, -1


class Zero:
    name = "zero"

    def evaluate(self, board):
        return 0


def kinds(board, col, score=0, **kw):
    ctx = move_context(board, MoveInfo(col=col, score=score, depth=1, pv=[col]), **kw)
    return {f.kind: f for f in forward_chain(ctx)}


def board_from(rows_bottom_up):
    arr = np.zeros((6, 7), dtype=np.int8)
    for r, row in enumerate(rows_bottom_up):
        arr[r, :len(row)] = row
    return Board.from_absolute(arr)


# X to move. O has row 1 cols 1-3: playable win at (1,4), unplayable at (1,0).
TRAP_BOARD = board_from([[0, X, X, O, X, X, 0],
                         [0, O, O, O, 0, 0, 0]])
# X to move. Playing col 3 (row 1) gives X row-1 cols 1-3, both ends unplayable.
SETUP_BOARD = board_from([[0, O, O, X, 0, 0, O],
                          [0, X, X, 0, 0, 0, 0]])


# ------------------------------------------------------------------ facts
def test_69_distinct_lines():
    assert len(LINES) == 69 == len(set(LINES))
    assert all(len(set(line)) == 4 for line in LINES)


def test_threat_and_playable_cells():
    arr = TRAP_BOARD.to_array()            # X to move -> X = +1
    assert set(threat_cells(arr, -1)) == {(1, 0), (1, 4)}
    assert (1, 4) in playable_cells(TRAP_BOARD)
    assert (1, 0) not in playable_cells(TRAP_BOARD)


def test_row_parity_bottom_is_odd():
    assert is_odd_row(0) and not is_odd_row(1)


# --------------------------------------------------------------- concepts
def test_hierarchy_and_rank():
    assert ancestors("fork") == ["fork", "attack", "tactic", "concept"]
    assert is_a("block", "tactic") and not is_a("centre", "tactic")
    assert rank(["centre", "block", "win", "fork", "block"]) == ["win", "block", "fork"]


# ------------------------------------------------------------------ rules
def test_win_only():
    f = kinds(Board.from_moves("121212"), 0)
    assert set(f) == {"win"}
    assert f["win"].cells[0] == (3, 0)


def test_block():
    f = kinds(Board.from_moves("12121"), 0)      # O must stop X's column-1 stack
    assert "block" in f and f["block"].cells[0] == (3, 0)


def test_fork_and_centre():
    f = kinds(Board.from_moves("2233"), 3)       # X: bottom cols 1,2 + 3 -> ends 0 and 4
    assert {"fork", "centre", "threat"} <= set(f)
    assert sorted(f["fork"].cells) == [(0, 0), (0, 4)]
    assert "setup" not in f


def test_trap_and_block_on_trap_board():
    assert "trap" in kinds(TRAP_BOARD, 0)
    assert "block" in kinds(TRAP_BOARD, 4)
    assert "trap" not in kinds(TRAP_BOARD, 4)


def test_setup_unplayable_threats_with_parity():
    f = forward_chain(move_context(SETUP_BOARD, MoveInfo(3, 0, 1, [3])))
    setups = sorted(x.cells[0] for x in f if x.kind == "setup")
    assert setups == [(1, 0), (1, 4)]
    assert all(x.detail == "even" for x in f if x.kind == "setup")
    assert not any(x.kind == "fork" for x in f)


def test_sacrifice():
    class FiftyForMover:                         # child scores +50 for the opponent
        name = "x"

        def evaluate(self, board):
            return 50
    b = Board.from_moves("44")
    assert "sacrifice" in kinds(b, 0, score=100, evaluator=FiftyForMover())
    assert "sacrifice" not in kinds(b, 0, score=100)          # no evaluator -> skipped
    assert "sacrifice" not in kinds(b, 0, score=-100, evaluator=FiftyForMover())


def test_detect_facts_fills_every_move():
    b = Board.from_moves("12121")
    trace = detect_facts(search(b, Zero(), max_depth=2))
    assert trace.moves[0].facts and all(isinstance(m.facts, list) for m in trace.moves.values())


# ---------------------------------------------------------------- explain
def test_explanation_mentions_block():
    trace = Agent(Zero(), time_limit=0.3).analyse(Board.from_moves("12121"))
    assert trace.chosen == 0
    e = explain_move(trace)
    assert e.concepts[0] == "block" and "block" in e.sentence
    assert all(f.kind in e.concepts for f in e.facts)


def test_no_rule_falls_back_to_score_only():
    b = Board.empty()
    trace = SearchTrace(board=b, chosen=0, depth=1, nodes=1, time_s=0, evaluator="zero",
                        static_score=0, moves={0: MoveInfo(0, 0, 1, [0])})
    e = explain_move(trace)
    assert e.concepts == [] and "column 1" in e.sentence


def test_agent_uses_rules():
    from c4.game import GameState
    g = GameState()
    for c in (0, 1, 0, 1, 0):
        g.apply_move(c)
    result = Agent(Zero(), time_limit=0.3).play_turn(g)
    assert result.col == 0 and "block" in result.explanation.concepts


# ------------------------------------------------------------- claim check
def test_claim_check_all_correct_small_run():
    total, correct, wrong = run(n=40, seed=1)
    assert sum(total.values()) > 0 and not wrong
