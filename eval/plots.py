"""Turn the result files into the plots used in the report.         OWNER: Mani

Reads whatever exists under results/ and skips what does not, so you can run it any
time:   python -m eval.plots            (writes PNGs to results/plots/)

  training.png          training and validation error per epoch   <- results/training/round*.json
  node_counts.png       nodes searched per configuration          <- results/node_counts.csv
                        (create it with:  python -m eval.node_counts --depth 6 > results/node_counts.csv)
  match.png             win/draw/loss of the network vs heuristic <- results/match/*.json
  solver_agreement.png  accuracy vs solver, by game stage         <- results/solver_agreement/agreement.json
  explanation_ratings.png  mean rating, agent vs score-only       <- results/user_study/analysis.json
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RESULTS = Path("results")


def _save(fig, name: str, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_training(out: Path) -> list[Path]:
    paths = []
    for f in sorted((RESULTS / "training").glob("round*.json")):
        d = json.loads(f.read_text())
        h = d["history"]
        epochs = [e["epoch"] for e in h]
        fig, ax = plt.subplots(1, 2, figsize=(9, 3.4))
        ax[0].plot(epochs, [e["train_mse"] for e in h], marker="o", label="train")
        ax[0].plot(epochs, [e["val_mse"] for e in h], marker="o", label="validation")
        if "test" in d:
            ax[0].axhline(d["test"]["baseline_mse"], ls="--", color="grey", label="predict-the-mean")
        ax[0].set(xlabel="epoch", ylabel="mean squared error", title=f"{f.stem}: loss")
        ax[0].legend()
        ax[1].plot(epochs, [100 * e["val_sign_acc"] for e in h], marker="o", color="tab:green")
        ax[1].set(xlabel="epoch", ylabel="validation: right side winning (%)",
                  title=f"{f.stem}: sign accuracy")
        paths.append(_save(fig, f"training_{f.stem}.png", out))
    return paths


def plot_node_counts(out: Path) -> list[Path]:
    f = RESULTS / "node_counts.csv"
    if not f.exists():
        return []
    rows = list(csv.DictReader(open(f)))
    configs = ["baseline", "ordering", "tt", "tt+ordering"]
    positions = sorted({r["position"] for r in rows}, key=lambda p: (len(p), p))
    fig, ax = plt.subplots(figsize=(7, 3.6))
    width = 0.2
    for i, c in enumerate(configs):
        vals = [next((int(r["nodes"]) for r in rows if r["position"] == p and r["configuration"] == c), 0)
                for p in positions]
        ax.bar([x + i * width for x in range(len(positions))], vals, width, label=c)
    ax.set_xticks([x + 1.5 * width for x in range(len(positions))])
    ax.set_xticklabels([p or "(empty)" for p in positions])
    ax.set(yscale="log", ylabel="nodes searched (log scale)", xlabel="position (moves played)",
           title=f"Search effort at depth {rows[0]['requested_depth']}")
    ax.legend()
    return [_save(fig, "node_counts.png", out)]


def plot_match(out: Path) -> list[Path]:
    paths = []
    for f in sorted((RESULTS / "match").glob("*.json")):
        s = json.loads(f.read_text())
        fig, ax = plt.subplots(figsize=(5, 3))
        counts = [s["a_wins"], s["draws"], s["b_wins"]]
        names = [f"{s['config']['a']} wins", "draws", f"{s['config']['b']} wins"]
        ax.bar(names, counts, color=["tab:green", "tab:grey", "tab:red"])
        lo, hi = s["a_score_wilson95"]
        ax.set(ylabel="games", title=f"{s['games']} games, {s['config']['time_limit']}s per move\n"
               f"{s['config']['a']} score {100 * s['a_score']:.1f}% (95% CI {100 * lo:.0f}-{100 * hi:.0f}%)")
        paths.append(_save(fig, f"match_{f.stem}.png", out))
    return paths


def plot_agreement(out: Path) -> list[Path]:
    f = RESULTS / "solver_agreement" / "agreement.json"
    if not f.exists():
        return []
    s = json.loads(f.read_text())
    names = list(s["evaluators"])
    buckets = list(s["by_ply"])
    fig, ax = plt.subplots(figsize=(7, 3.6))
    width = 0.8 / max(1, len(names))
    for i, n in enumerate(names):
        ax.bar([x + i * width for x in range(len(buckets))],
               [100 * s["by_ply"][b][n] for b in buckets], width, label=n)
    ax.axhline(100 * s["target"], ls="--", color="grey", label="80% target")
    ax.set_xticks([x + 0.4 - width / 2 for x in range(len(buckets))])
    ax.set_xticklabels(buckets)
    ax.set(xlabel="stones on the board", ylabel="right side winning (%)", ylim=(0, 100),
           title="Agreement with the perfect solver (won/lost positions)")
    ax.legend()
    return [_save(fig, "solver_agreement.png", out)]


def plot_ratings(out: Path) -> list[Path]:
    f = RESULTS / "user_study" / "analysis.json"
    if not f.exists():
        return []
    d = json.loads(f.read_text())["dimensions"]
    dims = list(d)
    fig, ax = plt.subplots(figsize=(6, 3.4))
    for i, (key, label) in enumerate((("agent_mean", "agent explanation"),
                                      ("baseline_mean", "score only"))):
        ax.bar([x + i * 0.38 for x in range(len(dims))], [d[k][key] for k in dims], 0.38, label=label)
    ax.set_xticks([x + 0.19 for x in range(len(dims))])
    ax.set_xticklabels(dims)
    ax.set(ylim=(1, 5), ylabel="mean rating (1-5)", title="Explanation ratings")
    ax.legend()
    return [_save(fig, "explanation_ratings.png", out)]


def main(argv=None):
    out = RESULTS / "plots"
    made = []
    for fn in (plot_training, plot_node_counts, plot_match, plot_agreement, plot_ratings):
        made += fn(out)
    print("\n".join(str(p) for p in made) or "nothing to plot yet (no result files found)")


if __name__ == "__main__":
    main()
