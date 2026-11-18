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

# (file stem in results/match, label in the report), the equal-time run first
MATCH_RUNS = [("nvh_fixed", "After the clock fix (equal time)"),
              ("network_vs_heuristic", "Before the fix, run 1"),
              ("mani_run_6workers", "Before the fix, run 2 (6 workers)")]


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
    m = load(R / "match" / "nvh_fixed.json")     # the equal-time run (after the search clock fix)
    rows.append(("Playing strength (network vs heuristic, equal-time run)", "network wins >= 55% of 200 games",
                 (f"{m['a_wins']}W {m['draws']}D {m['b_wins']}L of {m['games']}, score {pct(m['a_score'])} "
                  f"(95% CI {ci(m['a_score_wilson95'])})") if m else "NOT RUN YET",
                 (yes(m["target_met"]) + ("" if m["target_met"] == m["target_clearly_met"]
                                         else " (CI includes 55%)")) if m else "-"))
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
    parts = ["# Testing and evaluation", "",
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

    runs = []
    for stem, label in MATCH_RUNS:
        m = load(R / "match" / f"{stem}.json")
        if m:
            runs.append((label, m))
    if runs:
        rows = [(label, f"{m['a_wins']}-{m['draws']}-{m['b_wins']}", pct(m["a_score"]),
                 ci(m["a_score_wilson95"]), m["config"]["workers"], yes(m["target_met"]))
                for label, m in runs]
        parts += ["## Playing strength", "",
                  "Network evaluator against the hand-written evaluator, 200 games per run, 1 s per move, "
                  "100 random openings of 2 to 8 plies each played twice with the colours swapped. "
                  "Draws count half. The first two runs were played before a bug in the search clock was "
                  "fixed: the clock was checked only every 1024 nodes, so the network, which is slower per "
                  "node, overran its 1 s per move (1.3 to 1.7 s) while the heuristic stayed at 1 s. "
                  "The run after the fix (checks every 64 nodes) is the only equal-time comparison and is "
                  "the one used for the verdict. All three are reported.", "",
                  table(["Run", "W-D-L (network)", "Network score", "95% CI (Wilson)", "Workers",
                         "55% target"], rows), "",
                  "None of the runs reached the 55% target. Within the intervals the network is not "
                  "distinguishable from the hand-written evaluator at equal time per move.", ""]
    sa = load(R / "solver_agreement" / "agreement.json")
    if sa:
        parts += ["## Agreement with the perfect solver", "",
                  f"{sa['positions']} positions of {sa['min_ply']} to {sa['max_ply']} stones (seed "
                  f"{sa['seed']}), labelled win/draw/loss by the solver; "
                  f"{sa['excluded_training_positions']} position keys (every training position and its mirror "
                  f"image) were excluded, so no test position was seen in training. "
                  f"Solver labels: {sa['solver_outcome_counts']}.", ""]
        rows = [(n, pct(e["decisive_accuracy"]), ci(e["decisive_accuracy_wilson95"]),
                 pct(e["three_class_accuracy"])) for n, e in sa["evaluators"].items()]
        parts += [table(["Evaluator", "Right side winning (won/lost positions)", "95% CI",
                         "Three-class (draw band)"], rows), "",
                  f"The headline figure is the first accuracy column. The three-class column treats a "
                  f"score with absolute value up to {sa['draw_band']:g} as a predicted draw; that band "
                  f"suits the network's scale and not the hand-written evaluator's, so the heuristic's "
                  f"three-class figure is not a fair measure and should not be quoted.", ""]
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
              study_limitation(), "",
              "## How to reproduce", "", "See `docs/EVAL.md` for the exact commands.", ""]
    return "\n".join(parts)


def study_limitation() -> str:
    """Describe the sample of the rating study from items.csv (or generically if absent)."""
    import csv
    f = R / "user_study" / "items.csv"
    base = ("* The rating study used 30 randomly sampled mid-game positions (8 to 28 stones). "
            "Only positions where the agent's explanation differed from the score-only sentence "
            "were used")
    if f.exists():
        with open(f, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        if rows and "explained_share" in rows[0]:
            return base + f" ({100 * float(rows[0]['explained_share']):.0f}% of the sampled positions qualified)."
    return base + "."


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
