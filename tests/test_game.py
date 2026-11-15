from c4.game import GameState
from c4.stub_agent import StubAgent


def test_apply_move():
    g = GameState()
    g.apply_move(3)
    g.apply_move(2)
    assert g.history == [3, 2]
    assert g.board.num_moves == 2


def test_stub_agent_returns_legal_move():
    g = GameState()
    g.apply_move(3)
    result = StubAgent().play_turn(g)
    assert result.col in g.board.legal_moves()
    assert result.trace.chosen == result.col