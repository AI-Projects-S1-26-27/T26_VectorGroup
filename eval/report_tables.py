"""Write the evaluation section of the report from the result files.     OWNER: Mani

    python -m eval.report_tables            ->  docs/report/mani.md

Every number comes from a file in results/ (nothing is typed by hand). Anything not run
yet is written as "NOT RUN YET" so you can see what is missing. Run it again after each
experiment. Read the generated text before submitting: the sentences about what the results
mean are yours to check.
"""
from __future__ import annotations

import json
from pathlib import Path

R = Path("results")


def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def ci(pair):
    return f"{pct(pair[0], 0)}-{pct(pair[1], 0)}"


def yes(flag):
    return "met" if flag else "NOT met"


def summary_rows() -> list[tuple[str, str, str, str]]:
    """(experiment, proposal target, measured, verdict)"""
    rows = []
    nc = load(R / "node_counts_summary.json")
    rows.append(("Search efficiency (100 positions, depth 8)", ">= 10x fewer nodes",
                 f"{nc['aggregate_node_reduction']:.2f}x fewer (tt+ordering vs baseline)" if nc else "NOT RUN YET",
                 yes(nc["target_met"]) if nc else "-"))
    m = load(R / "match" / "network_vs_heuristic.json")
    rows.append(("Playing strength (network vs heuristic)", "network wins >= 55% of 200 games",
                 (f"{m['a_wins']}W {m['draws']}D {m['b_wins']}L of {m['games']}, score {pct(m['a_score'])} "
                  f"(95% CI {ci(m['a_score_wilson95'])})") if m else "NOT RUN YET",
                 yes(m["target_met"]) + ("" if not m or m["target_met"] == m["target_clearly_met"]
                                        else " (CI includes 55%)") if m else "-"))
    sa = load(R / "solver_agreement" / "agreement.json")
    if sa and "network" in sa["evaluators"]:
        e = sa["evaluators"]["network"]
        rows.append(("Network vs perfect solver", ">= 80% right side winning",
                     f"{pct(e['decisive_accuracy'])} on {e['decisive_positions']} won/lost positions "
                     f"(95% CI {ci(e['decisive_accuracy_wilson95'])})",
                     yes(e["decisive_accuracy"] >= sa["target"])))
    else:
        rows.append(("Network vs perfect solver", ">= 80% right side winning", "NOT RUN YET", "-"))
    cc = load(R / "claim_check.json")
    rows.append(("Explanation claims checked by brute force", ">= 98% correct",
                 f"{cc['correct']}/{cc['claims']} ({pct(cc['accuracy'])}) on {cc['positions']} positions" if cc else "NOT RUN YET",
                 yes(cc["target_met"]) if cc else "-"))
    an = load(R / "user_study" / "analysis.json")
    if an:
        d = an["dimensions"]
        txt = "; ".join(f"{k} {v['agent_mean']:.2f} vs {v['baseline_mean']:.2f}" for k, v in d.items())
        rows.append(("Rating study (agent vs score-only)", "agent rated higher",
                     f"{an['raters']} raters: {txt}",
                     "higher on " + ", ".join(k for k, v in d.items() if v["mean_difference"] > 0) or "none"))
    else:
        rows.append(("Rating study (agent vs score-only)", "agent rated higher", "NOT RUN YET", "-"))
    for name in ("heuristic", "network"):
        rb = load(R / "robustness" / name / "robustness.json")
        rows.append((f"Robustness ({name} agent)", ">= 95% sensible, < 2 s",
                     f"{rb['sensible']}/{rb['questions']} sensible, slowest {rb['max_seconds']:.2f}s" if rb else "NOT RUN YET",
                     yes(rb["target_met"] and rb["under_2s_rate"] == 1.0) if rb else "-"))
    return rows


def table(header, rows) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def build() -> str:
    parts = ["# Mani: testing and evaluation", "",
             "## Scope", "",
             "Mani's modules are `eval/solver.py`, `eval/match.py`, `eval/solver_agreement.py`, "
             "`eval/robustness.py`, `eval/user_study/`, `eval/plots.py`, `eval/stats.py` and "
             "`eval/report_tables.py`, with their tests. They only read the agent and never "
             "change it. The perfect solver (negamax with alpha-beta, bitboards, a transposition "
             "table and pruning of losing moves, following Pons [2]) is used for testing only, "
             "never inside the agent; it was checked against a plain brute-force search on "
             "late-game positions.", "",
             "## Results against the proposal's targets", "",
             table(["Experiment", "Proposal target", "Measured", "Verdict"], summary_rows()), ""]

    m = load(R / "match" / "network_vs_heuristic.json")
    if m:
        c = m["config"]
        parts += ["## Playing strength", "",
                  f"{m['games']} games between the network evaluator and the hand-written evaluator, "
                  f"{c['time_limit']} s per move for both (equal time, not equal depth). "
                  f"{m['games'] // 2} random openings of 2 to 8 plies were each played twice with the "
                  f"colours swapped, so neither side benefits from the openings. Draws count half. "
                  f"The network scored {pct(m['a_score'])} (Wilson 95% CI {ci(m['a_score_wilson95'])}; "
                  f"bootstrap over openings {ci(m['a_score_bootstrap95'])}). Excluding draws it won "
                  f"{pct(m['a_win_rate_excluding_draws'])} of decisive games. The 55% target was "
                  f"{yes(m['target_met'])}.", ""]
    sa = load(R / "solver_agreement" / "agreement.json")
    if sa:
        parts += ["## Agreement with the perfect solver", "",
                  f"{sa['positions']} positions of {sa['min_ply']} to {sa['max_ply']} stones (seed "
                  f"{sa['seed']}), labelled win/draw/loss by the solver; "
                  f"{sa['excluded_training_positions']} training positions were excluded. "
                  f"Solver labels: {sa['solver_outcome_counts']}.", ""]
        rows = [(n, pct(e["decisive_accuracy"]), ci(e["decisive_accuracy_wilson95"]),
                 pct(e["three_class_accuracy"])) for n, e in sa["evaluators"].items()]
        parts += [table(["Evaluator", "Right side winning (won/lost positions)", "95% CI",
                         "Three-class (draw band)"], rows), ""]
    an = load(R / "user_study" / "analysis.json")
    if an:
        rows = [(k, f"{v['agent_mean']:.2f}", f"{v['baseline_mean']:.2f}",
                 f"{v['mean_difference']:+.2f}", ci2(v["difference_bootstrap95"]),
                 f"{v['sign_flip_p']:.3f}") for k, v in an["dimensions"].items()]
        parts += ["## Rating study", "",
                  f"{an['raters']} raters, {an['ratings']} ratings. Each rater saw 30 positions, half with "
                  "the agent's explanation and half with the score-only sentence (two counterbalanced "
                  "sheets). Means are per rater; the p value is a paired sign-flip permutation test over raters.", "",
                  table(["Question", "Agent", "Score only", "Difference", "95% CI", "p"], rows), ""]
    parts += ["## Limitations", "",
              "* The solver positions come from a sampler (random and shallow-search moves), not from "
              "real human games, so the accuracy applies to that mix.",
              "* Match results depend on the machine: search is time-limited, so a slower or busier "
              "machine weakens both players. Parallel workers were limited to leave a core free.",
              "* The claim checker confirms that the stated facts are true, not that an explanation is "
              "helpful; usefulness is what the rating study measures, with a small number of raters.",
              "* The rating study used positions where the rule layer produced an explanation; quiet "
              "positions fall back to the score-only sentence, so the study does not cover them.", "",
              "## How to reproduce", "", "See `docs/EVAL.md` for the exact commands.", ""]
    return "\n".join(parts)


def ci2(pair):
    return f"{pair[0]:+.2f} to {pair[1]:+.2f}"


def main(argv=None):
    out = Path("docs/report/mani.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(), encoding="utf-8")
    print(f"wrote {out}")
    missing = [r[0] for r in summary_rows() if r[2] == "NOT RUN YET"]
    if missing:
        print("still missing:", "; ".join(missing))


if __name__ == "__main__":
    main()
