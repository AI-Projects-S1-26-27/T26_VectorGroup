"""Analyse the explanation ratings.                                    OWNER: Mani

Input: one CSV of ratings, one row per rating, columns
    rater, sheet, item, correctness, clarity, usefulness     (scores 1-5, sheet = A or B)
and results/user_study/key.json from build_study.py.

For each of the three questions: the mean rating of the agent's explanations and of
the score-only baseline, the paired difference per rater (each rater rated both kinds),
a bootstrap 95% interval over raters, and a paired sign-flip permutation test.

  python -m eval.user_study.analyse_ratings ratings.csv
Writes results/user_study/analysis.json
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from eval.stats import bootstrap_mean_ci, sign_flip_pvalue

DIMENSIONS = ("correctness", "clarity", "usefulness")


def load_ratings(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for d in DIMENSIONS:
            r[d] = float(r[d])
            if not 1 <= r[d] <= 5:
                raise ValueError(f"rating out of range 1-5: {r}")
        r["sheet"] = r["sheet"].strip().upper()
    return rows


def analyse(rows: list[dict], key: dict) -> dict:
    """key: {'A': {'1': 'agent', ...}, 'B': {...}} as written by build_study."""
    per: dict[str, dict[str, dict[str, list[float]]]] = {}   # rater -> dim -> cond -> ratings
    for r in rows:
        cond = key[r["sheet"]][str(int(float(r["item"])))]
        for d in DIMENSIONS:
            per.setdefault(r["rater"], {}).setdefault(d, {}).setdefault(cond, []).append(r[d])
    out = {"raters": len(per), "ratings": len(rows), "dimensions": {}}
    for d in DIMENSIONS:
        diffs, agent_means, base_means = [], [], []
        for rater, dims in per.items():
            c = dims.get(d, {})
            if c.get("agent") and c.get("baseline"):
                a = sum(c["agent"]) / len(c["agent"])
                b = sum(c["baseline"]) / len(c["baseline"])
                agent_means.append(a)
                base_means.append(b)
                diffs.append(a - b)
        n = len(diffs)
        lo, hi = bootstrap_mean_ci(diffs) if diffs else (float("nan"),) * 2
        out["dimensions"][d] = dict(
            raters_used=n,
            agent_mean=sum(agent_means) / n if n else float("nan"),
            baseline_mean=sum(base_means) / n if n else float("nan"),
            mean_difference=sum(diffs) / n if n else float("nan"),
            difference_bootstrap95=[lo, hi],
            sign_flip_p=sign_flip_pvalue(diffs) if diffs else float("nan"))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ratings")
    p.add_argument("--key", default="results/user_study/key.json")
    p.add_argument("--out", default="results/user_study/analysis.json")
    a = p.parse_args(argv)
    result = analyse(load_ratings(a.ratings), json.loads(Path(a.key).read_text()))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
