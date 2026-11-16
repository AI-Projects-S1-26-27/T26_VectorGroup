"""Tests for eval/robustness.py.                                      OWNER: Mani"""
from c4.agent import Agent
from c4.eval_heuristic import HeuristicEvaluator
from eval import robustness as rb

FALLBACK = ("You can ask: why did you play there? why not column 5? what if I play "
            "column 3? or who is winning?")


def test_question_set_is_big_and_varied():
    qs = rb.build_questions()
    assert len(qs) > 100
    assert {q[2] for q in qs} <= {"answer", "fallback", "either"}
    assert {q[3] for q in qs} <= set(rb.STATES) | {"mid"}
    cats = {q[1] for q in qs}
    assert {"why", "why_not", "what_if", "winning", "off_topic", "degenerate",
            "game_over", "full_column", "column_spelling"} <= cats


def test_game_situations_are_what_they_claim():
    agent = Agent(HeuristicEvaluator(), time_limit=0.1)
    start = rb.build_game("start", agent)
    assert start.last_trace is None
    mid = rb.build_game("mid", agent)
    assert mid.last_trace is not None and not mid.board.is_over()
    full = rb.build_game("full_column", agent)
    assert not full.board.can_play(3) and not full.board.is_over()
    over = rb.build_game("over", agent)
    assert over.board.is_over()


def test_judge_rules():
    ok = rb.judge
    assert ok("I blocked your three.", "answer", 0.1)[0]
    assert not ok("", "either", 0.1)[0]
    assert not ok(None, "either", 0.1)[0]
    assert not ok("Traceback (most recent call last)", "either", 0.1)[0]
    assert not ok("x" * (rb.MAX_CHARS + 1), "either", 0.1)[0]
    assert not ok("fine", "either", rb.TIME_LIMIT + 0.01)[0]
    assert not ok(FALLBACK, "answer", 0.1)[0]            # fallback to a real question
    assert ok(FALLBACK, "fallback", 0.1)[0]
    assert not ok("I don't know.", "fallback", 0.1)[0]   # should have listed the options
    assert rb.is_fallback(FALLBACK) and not rb.is_fallback("I played column 4.")


def test_a_well_behaved_answer_function_passes():
    def answer(question, game):
        low = question.lower()
        if len(low) > 200 or not any(w in low for w in ("why", "what if", "who")) \
                or game.board.is_over() or game.last_trace is None or "column 4" in low and \
                not game.board.can_play(3):
            return FALLBACK
        return "I played there because it was best."
    agent = Agent(HeuristicEvaluator(), time_limit=0.1)
    res = rb.run_check(answer, lambda s: rb.build_game(s, agent))
    summary = res["summary"]
    assert summary["questions"] == len(rb.build_questions())
    assert summary["under_2s_rate"] == 1.0
    assert 0 <= summary["sensible_rate"] <= 1


def test_crashes_and_slow_answers_count_as_failures(monkeypatch):
    def crash(question, game):
        raise RuntimeError("boom")
    agent = Agent(HeuristicEvaluator(), time_limit=0.1)
    res = rb.run_check(crash, lambda s: rb.build_game(s, agent), rb.build_questions()[:10])
    assert res["summary"]["sensible"] == 0 and res["summary"]["target_met"] is False
    assert all("crashed" in r["reason"] for r in res["rows"])

    monkeypatch.setattr(rb, "TIME_LIMIT", 0.0)
    res = rb.run_check(lambda q, g: "ok", lambda s: rb.build_game(s, agent), rb.build_questions()[:5])
    assert all("too slow" in r["reason"] for r in res["rows"])
