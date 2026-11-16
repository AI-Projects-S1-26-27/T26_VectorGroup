"""Tests for sentence templates and question answering.   OWNER: Aditya"""
import pytest

from c4.agent import Agent, score_only_explanation
from c4.board import Board
from c4.eval_heuristic import HeuristicEvaluator
from c4.explain.templates import render, advantage_text
from c4.game import GameState, TurnResult
from c4.qa.answers import answer
from c4.qa.parser import HELP
from c4.trace import Fact, MoveInfo, SearchTrace, WIN_SCORE


def fast_agent():
    return Agent(HeuristicEvaluator(), time_limit=0.05)


def game_after_agent_move(moves="4", agent=None):
    """Human (X) has played `moves`, then the agent answers."""
    agent = agent or fast_agent()
    board = Board.from_moves(moves)
    trace = agent.analyse(board)
    game = GameState(board=board, history=[int(c) - 1 for c in moves], human_first=True)
    game.record_agent_turn(TurnResult(col=trace.chosen, trace=trace,
                                      explanation=score_only_explanation(trace)))
    return game, trace


def hand_trace(board, chosen, scores, facts=None, pv=None):
    facts = facts or {}
    pv = pv or {}
    moves = {c: MoveInfo(col=c, score=scores[c], depth=6, pv=pv.get(c, [c]),
                         facts=facts.get(c, [])) for c in board.legal_moves()}
    return SearchTrace(board=board, chosen=chosen, depth=6, nodes=1, time_s=0.0,
                       evaluator="heuristic", static_score=0, moves=moves)


class Boom:
    def analyse(self, board):
        raise RuntimeError("engine down")


# ---------------------------------------------------------------- templates
def test_render_uses_only_given_facts():
    board = Board.from_moves("4")
    trace = hand_trace(board, 3, {c: 10 for c in board.legal_moves()})
    facts = [Fact("block", col=3, cells=[(0, 3)]), Fact("centre", col=3, cells=[(0, 3)])]
    text = render(["block", "centre"], facts, trace)
    assert text.startswith("I played column 4 because it blocks your four-in-a-row and "
                           "it takes the centre column")
    assert "fork" not in text and "win" not in text.split("because")[1].split(".")[0]


def test_render_fork_names_columns_and_setup_names_row():
    board = Board.from_moves("4")
    trace = hand_trace(board, 3, {c: 0 for c in board.legal_moves()})
    fork = Fact("fork", col=3, cells=[(1, 2), (1, 5)])
    setup = Fact("setup", col=1, cells=[(2, 1)], detail="even")
    text = render(["fork", "setup"], [fork, setup], trace)
    assert "2 threats at once (columns 3 and 6)" in text
    assert "column 2, row 3" in text


def test_render_without_concepts_and_decided_scores():
    board = Board.from_moves("4")
    win = hand_trace(board, 3, {c: 0 for c in board.legal_moves()} | {3: WIN_SCORE - 7})
    assert render([], [], win) == "I played column 4. I can force a win in 4 moves."
    lose = hand_trace(board, 3, {c: 0 for c in board.legal_moves()} | {3: -(WIN_SCORE - 8)})
    assert "losing by force" in render([], [], lose)


def test_advantage_bands():
    assert advantage_text(0) == "the position looks roughly balanced"
    assert "slight edge" in advantage_text(80) and "you appear" in advantage_text(-80)
    assert "advantage" in advantage_text(400)


# ---------------------------------------------------------------------- why
def test_why_returns_saved_explanation():
    game, trace = game_after_agent_move()
    assert answer("why did you play there?", game) == game.last_explanation.sentence


def test_why_before_any_move():
    game = GameState(board=Board.from_moves("4"), human_first=True)
    assert "haven't made a move" in answer("why did you play there?", game)


def test_stale_history_is_refused():
    game, _ = game_after_agent_move("4")
    game.board = Board.from_moves("1234567")            # unrelated position
    assert "does not match" in answer("why?", game)


# ------------------------------------------------------------------- why not
def test_why_not_compares_scores_and_shows_line():
    game, trace = game_after_agent_move()
    other = next(c for c in trace.moves if c != trace.chosen)
    text = answer(f"why not column {other + 1}?", game)
    assert f"instead of column {other + 1}" in text
    assert "Expected line:" in text and "me:" in text


def test_why_not_alternative_facts_are_worded_as_not_played():
    board = Board.from_moves("4")
    trap = Fact("trap", col=0, cells=[(1, 0)])
    trace = hand_trace(board, 3, {c: 5 for c in board.legal_moves()} | {0: -20},
                       facts={0: [trap]})
    game = GameState(board=board.play_unchecked(3), history=[3, 3], human_first=True,
                     last_trace=trace)
    text = answer("why not column 1?", game)
    assert "About column 1: it lets you win by playing on top" in text
    assert "still rated it best" not in text


def test_why_not_decided_loss_and_tie():
    board = Board.from_moves("4")
    scores = {c: 0 for c in board.legal_moves()} | {0: -(WIN_SCORE - 6)}
    trace = hand_trace(board, 3, scores)
    game = GameState(board=board.play_unchecked(3), human_first=True, last_trace=trace)
    # a loss in 6 plies from the root = 3 moves of the human's
    assert "after column 1 you can force a win in 3 moves" in answer("why not column 1?", game)
    assert "They tied" in answer("why not column 2?", game)


def test_why_not_forced_win_counts_my_moves():
    board = Board.from_moves("4")
    scores = {c: 0 for c in board.legal_moves()} | {3: WIN_SCORE - 7}   # win with my 4th move
    trace = hand_trace(board, 3, scores)
    game = GameState(board=board.play_unchecked(3), human_first=True, last_trace=trace)
    assert "column 4 lets me force a win in 4 moves" in answer("why not column 1?", game)


def test_long_expected_line_is_cut_cleanly():
    from c4.explain.templates import continuation_text
    assert continuation_text(list(range(7)) + [0], True) == (
        "Expected line: me: 1 -> you: 2 -> me: 3 -> you: 4 -> me: 5 -> you: 6 -> ...")
    assert continuation_text([3, 2], True) == "Expected line: me: 4 -> you: 3."


def test_why_not_chosen_and_full_column():
    game, trace = game_after_agent_move()
    assert "is the move I played" in answer(f"why not column {trace.chosen + 1}?", game)
    board = Board.from_moves("1111112")                   # column 1 is full, agent to move
    trace = hand_trace(board, 3, {c: 0 for c in board.legal_moves()})
    full = GameState(board=board.play_unchecked(3), human_first=True, last_trace=trace)
    text = answer("why not column 1?", full)
    assert "was full" in text and HELP in text


# ------------------------------------------------------------------- what if
def test_what_if_searches_a_copy_and_leaves_the_game_alone():
    game, trace = game_after_agent_move()
    before = (game.board, list(game.history), game.last_trace)
    col = game.board.legal_moves()[0] + 1
    text = answer(f"what if I play column {col}?", game, fast_agent())
    assert text.startswith(f"If you play column {col}, I would play column ")
    assert "your game has not changed" in text
    assert (game.board, game.history, game.last_trace) == before


def test_what_if_immediate_human_win_and_wrong_turn():
    board = Board.from_moves("112233")                    # X can finish 1-2-3-4 bottom row
    game = GameState(board=board, human_first=True)
    assert "you complete four in a row and win" in answer("what if I play column 4?", game)
    agent_turn = GameState(board=Board.from_moves("4"), human_first=True)  # agent's turn
    assert "Wait for my move" in answer("what if I play column 1?", agent_turn)


def test_what_if_full_column():
    game = GameState(board=Board.from_moves("111111"), human_first=True)
    text = answer("what if I play column 1?", game)
    assert "Column 1 is full" in text and HELP in text      # lists what can be asked


def test_search_failure_is_a_friendly_message():
    game, _ = game_after_agent_move()
    text = answer("what if I play column 3?", game, Boom())
    assert "can't search" in text and "engine down" not in text


# ------------------------------------------------------------- who is winning
def test_who_winning_reads_saved_trace():
    game, trace = game_after_agent_move()
    text = answer("who is winning?", game)
    assert f"{trace.depth} plies ahead" in text and "not a proven result" in text


def test_who_winning_decided_perspectives():
    # the saved trace starts before the agent's move; that move is already played,
    # so a win 7 plies from the trace's root is 6 plies (3 of my moves) from now
    board = Board.from_moves("4")
    win = hand_trace(board, 3, {c: 0 for c in board.legal_moves()} | {3: WIN_SCORE - 7})
    g = GameState(board=board.play_unchecked(3), human_first=True, last_trace=win)
    text = answer("who is winning?", g)
    assert text.startswith("I can force a win in 3 moves") and "6 plies" in text
    lose = hand_trace(board, 3, {c: 0 for c in board.legal_moves()} | {3: -(WIN_SCORE - 8)})
    g = GameState(board=board.play_unchecked(3), human_first=True, last_trace=lose)
    text = answer("who is winning?", g)
    assert text.startswith("You can force a win in 4 moves") and "7 plies" in text


def test_who_winning_right_after_a_fork_counts_from_now():
    # Naman's example: agent is X, moves 2 2 3 3, agent plays 4 and makes two threats.
    agent = fast_agent()
    board = Board.from_moves("2233")
    trace = agent.analyse(board)
    game = GameState(board=board, history=[1, 1, 2, 2], human_first=False)
    game.record_agent_turn(TurnResult(col=trace.chosen, trace=trace,
                                      explanation=score_only_explanation(trace)))
    text = answer("who is winning?", game)
    assert text.startswith("I can force a win in 1 move ") and "2 plies" in text


def test_who_winning_without_trace_searches_with_human_to_move():
    game = GameState(board=Board.empty(), human_first=True)
    text = answer("who is winning?", game, fast_agent())
    assert "plies ahead" in text


def test_agent_playing_first_uses_the_right_perspective():
    board = Board.empty()
    trace = hand_trace(board, 3, {c: 0 for c in board.legal_moves()} | {3: 300})
    game = GameState(board=board.play_unchecked(3), human_first=False, last_trace=trace)
    assert "I appear to have the advantage" in answer("who is winning?", game)


# -------------------------------------------------------------- other inputs
def test_buttons_and_text_agree_and_bad_input_gets_help():
    game, _ = game_after_agent_move()
    assert answer({"intent": "who_winning"}, game) == answer("who is winning?", game)
    assert answer({"intent": "why_not", "column": 99}, game).startswith("Choose one column")
    reply = answer("tell me a joke", game)
    assert "why not column 5" in reply


def test_finished_game():
    board = Board.from_moves("1122334")                   # X wins on the bottom row
    game = GameState(board=board, human_first=True)
    text = answer("why?", game)
    assert text.startswith("The game is over: you won") and HELP in text


def test_unknown_fact_kind_is_skipped_not_a_crash():
    from c4.explain.templates import phrases_for
    facts = [Fact("brand_new_rule", col=3, cells=[(0, 3)]), Fact("centre", col=3, cells=[(0, 3)])]
    assert phrases_for(["brand_new_rule", "centre"], facts) == [
        "it takes the centre column, which is part of the most lines of four"]
