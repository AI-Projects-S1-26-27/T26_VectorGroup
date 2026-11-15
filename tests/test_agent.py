from c4.agent import Agent, score_only_explanation
from c4.board import Board
from c4.game import GameState
from c4.search import search


class ZeroEvaluator:
    name = "zero"

    def evaluate(self, board):
        return 0


def make_agent():
    return Agent(ZeroEvaluator(), time_limit=0.2)


def test_analyse_covers_all_legal_moves():
    b = Board.from_moves("4453")
    trace = make_agent().analyse(b)
    assert sorted(trace.moves) == b.legal_moves()


def test_play_turn_returns_legal_move_and_sentence():
    g = GameState()
    g.apply_move(3)                      # human opens in the middle
    result = make_agent().play_turn(g)
    assert result.col in g.board.legal_moves()
    assert result.trace.chosen == result.col
    assert isinstance(result.explanation.sentence, str) and result.explanation.sentence


def test_play_turn_does_not_change_game():
    g = GameState()
    g.apply_move(3)
    make_agent().play_turn(g)
    assert g.board.num_moves == 1 and g.last_trace is None


def test_record_agent_turn_updates_game():
    g = GameState()
    g.apply_move(3)
    result = make_agent().play_turn(g)
    g.record_agent_turn(result)
    assert g.board.num_moves == 2
    assert g.history[-1] == result.col
    assert g.last_trace is result.trace
    assert g.last_explanation is result.explanation
    assert g.last_trace.board.num_moves == 1      # trace.board = position BEFORE the agent moved


def test_score_only_sentence_for_forced_win():
    trace = search(Board.from_moves("121212"), ZeroEvaluator(), time_limit=0.5)
    text = score_only_explanation(trace).sentence
    assert "column 1" in text and "win" in text and "1 move." in text