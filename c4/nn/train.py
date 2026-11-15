"""Train the value network on self-play data.                 OWNER: Sriyanth

    python -m c4.nn.train --data data/selfplay/round_1 --out models/round1.pt
    python -m c4.nn.train --data data/selfplay/round_1 data/selfplay/round_2 \\
           --init models/round1.pt --out models/round2.pt          # round 2
    ... --tromp data/connect-4.data      # also report accuracy on Tromp's UCI set

What it does (proposal 4.2)
  1. Load Veer's shards and split them BY GAME (c4.selfplay.dataset.split_by_game):
       test  (10% of games, never used for any decision; reported at the end)
       val   (10% of the remaining games, used to pick the best epoch)
       train (the rest)
     Positions also seen in training games are removed from val/test (strict split).
  2. Train with mean squared error and Adam. Each batch, a random half of the
     boards is mirrored left-right (Connect-4 is symmetric), which is the same
     as training on the mirrored data set without storing it twice.
  3. Keep the epoch with the lowest validation loss; stop early if it has not
     improved for --patience epochs or --max-minutes have passed.
  4. Save models/<name>.pt, copy it to models/nn_latest.pt (what NNEvaluator()
     loads), and write the loss curves to results/training/<name>.json for the report.

Metrics
  mse        mean squared error against the game result (+1 / 0 / -1)
  baseline   mse of always predicting the mean training label (the network must beat it)
  sign_acc   on positions whose game was won or lost: how often the network
             gets the winner right (sign of the output)
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from c4.board import Board, HEIGHT, WIDTH
from c4.nn.model import C4Net, count_parameters, load_checkpoint, save_checkpoint
from c4.selfplay.dataset import encode_batch, load_positions, split_by_game

REPO_ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ data
def to_tensors(data) -> tuple[torch.Tensor, torch.Tensor]:
    """PositionData -> (uint8 planes N x 3 x 6 x 7, float labels N). uint8 keeps memory low."""
    x = torch.from_numpy(encode_batch(data.position, data.mask))
    y = torch.from_numpy(data.result.astype(np.float32))
    return x, y


def load_tromp(path) -> tuple[torch.Tensor, torch.Tensor]:
    """Tromp's UCI Connect-4 set (connect-4.data, unpacked from connect-4.data.Z).

    Each line: 42 cells a1..a6, b1..b6, ..., g1..g6 (column by column, row 1 = bottom)
    with values x / o / b, then win / loss / draw for x. All positions have 8 stones,
    so x is to move and the label is already for the player to move."""
    val = {"x": 1, "o": -1, "b": 0}
    lab = {"win": 1.0, "loss": -1.0, "draw": 0.0}
    pos, msk, ys = [], [], []
    for line in Path(path).read_text().splitlines():
        parts = line.strip().split(",")
        if len(parts) != 43:
            continue
        arr = np.zeros((HEIGHT, WIDTH), dtype=np.int8)
        for i, v in enumerate(parts[:42]):
            arr[i % HEIGHT, i // HEIGHT] = val[v]
        b = Board.from_absolute(arr)
        pos.append(b.position)
        msk.append(b.mask)
        ys.append(lab[parts[42]])
    x = torch.from_numpy(encode_batch(np.array(pos, dtype=np.uint64),
                                      np.array(msk, dtype=np.uint64)))
    return x, torch.tensor(ys, dtype=torch.float32)


# ------------------------------------------------------------------ eval
@torch.no_grad()
def predict(model: nn.Module, x: torch.Tensor, device: str, batch_size: int = 4096) -> torch.Tensor:
    model.eval()
    out = [model(x[i:i + batch_size].to(device).float()).cpu()
           for i in range(0, len(x), batch_size)]
    return torch.cat(out) if out else torch.empty(0)


def metrics(model, x, y, device, train_mean: float) -> dict:
    if len(y) == 0:
        return {"n": 0}
    p = predict(model, x, device)
    decided = y != 0
    return {
        "n": int(len(y)),
        "mse": float(((p - y) ** 2).mean()),
        "baseline_mse": float(((train_mean - y) ** 2).mean()),
        "sign_acc": float((torch.sign(p[decided]) == y[decided]).float().mean())
        if decided.any() else None,
    }


# ------------------------------------------------------------------ train
def train(round_dirs, out, epochs: int = 15, batch_size: int = 512, lr: float = 1e-3,
          weight_decay: float = 1e-4, test_frac: float = 0.1, val_frac: float = 0.1,
          patience: int = 3, max_minutes: float | None = None, init: str | None = None,
          seed: int = 0, device: str | None = None, latest: bool = True,
          tromp: str | None = None, results_dir=None, log=print) -> dict:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(out)

    data = load_positions(round_dirs)
    rest, test = split_by_game(data, test_frac, seed=seed)
    train_d, val = split_by_game(rest, val_frac, seed=seed + 1)
    xtr, ytr = to_tensors(train_d)
    xva, yva = to_tensors(val)
    xte, yte = to_tensors(test)
    train_mean = float(ytr.mean())
    log(f"games {data.num_games()}  positions: train {len(ytr)}  val {len(yva)}  "
        f"test {len(yte)}  (device {device})")

    if init:
        model, _ = load_checkpoint(init, device)
        log(f"starting from {init}")
    else:
        model = C4Net().to(device)
    log(f"parameters: {count_parameters(model):,}")

    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    loss_fn = nn.MSELoss()
    history, best_val, best_state, bad = [], float("inf"), None, 0
    start = time.perf_counter()

    for epoch in range(1, epochs + 1):
        model.train()
        perm = torch.from_numpy(rng.permutation(len(ytr)))
        total, seen = 0.0, 0
        for i in range(0, len(perm), batch_size):
            idx = perm[i:i + batch_size]
            xb = xtr[idx].float()
            flip = torch.rand(len(idx)) < 0.5                  # mirror half the batch
            xb[flip] = xb[flip].flip(-1)
            xb, yb = xb.to(device), ytr[idx].to(device)
            loss = loss_fn(model(xb), yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss) * len(idx)
            seen += len(idx)
        v = metrics(model, xva, yva, device, train_mean)
        row = {"epoch": epoch, "train_mse": total / max(1, seen), "val_mse": v.get("mse"),
               "val_sign_acc": v.get("sign_acc"), "minutes": (time.perf_counter() - start) / 60}
        history.append(row)
        log(f"epoch {epoch:2d}  train {row['train_mse']:.4f}  val {row['val_mse']:.4f}  "
            f"val sign acc {row['val_sign_acc']}  ({row['minutes']:.1f} min)")
        if v.get("mse", float("inf")) < best_val:
            best_val, bad = v["mse"], 0
            best_state = {k: t.detach().cpu().clone() for k, t in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                log("validation loss stopped improving, stopping")
                break
        if max_minutes is not None and row["minutes"] >= max_minutes:
            log("time budget used up, stopping")
            break

    if best_state is not None:
        model.load_state_dict(best_state)
    model.to(device)
    report = {
        "rounds": [str(d) for d in ([round_dirs] if isinstance(round_dirs, (str, Path))
                                    else round_dirs)],
        "init": init, "parameters": count_parameters(model),
        "settings": dict(epochs=epochs, batch_size=batch_size, lr=lr,
                         weight_decay=weight_decay, seed=seed),
        "games": int(data.num_games()), "train_positions": int(len(ytr)),
        "history": history,
        "test": metrics(model, xte, yte, device, train_mean),
    }
    if tromp:
        xt, yt = load_tromp(tromp)
        report["tromp"] = metrics(model, xt, yt, device, train_mean)
    log(f"test: {report['test']}")
    if tromp:
        log(f"tromp: {report['tromp']}")

    model.cpu()
    save_checkpoint(model, out, info={k: report[k] for k in ("rounds", "parameters", "test")})
    if latest:
        shutil.copyfile(out, out.parent / "nn_latest.pt")
    res = Path(results_dir) if results_dir else REPO_ROOT / "results" / "training"
    res.mkdir(parents=True, exist_ok=True)
    (res / f"{out.stem}.json").write_text(json.dumps(report, indent=2))
    log(f"saved {out}" + (f" and {out.parent / 'nn_latest.pt'}" if latest else "")
        + f"; curves in {res / (out.stem + '.json')}")
    return report


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Train the Connect-4 value network.")
    p.add_argument("--data", nargs="+", required=True, help="self-play round folder(s)")
    p.add_argument("--out", default="models/round1.pt")
    p.add_argument("--init", default=None, help="start from these weights (round 2+)")
    p.add_argument("--epochs", type=int, default=15)
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--patience", type=int, default=3)
    p.add_argument("--max-minutes", type=float, default=None)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--device", default=None, help="cpu or cuda (default: cuda if available)")
    p.add_argument("--no-latest", action="store_true", help="do not overwrite models/nn_latest.pt")
    p.add_argument("--tromp", default=None, help="path to connect-4.data (extra test set)")
    a = p.parse_args(argv)
    train(a.data, a.out, epochs=a.epochs, batch_size=a.batch_size, lr=a.lr,
          weight_decay=a.weight_decay, patience=a.patience, max_minutes=a.max_minutes,
          init=a.init, seed=a.seed, device=a.device, latest=not a.no_latest, tromp=a.tromp)


if __name__ == "__main__":
    main()
