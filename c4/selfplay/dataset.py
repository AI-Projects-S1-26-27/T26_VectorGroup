"""Turning self-play shards into training data for the network.   OWNER: Veer

    data = load_positions(["data/selfplay/round_1"])     # every saved position
    train, test = split_by_game(data, test_frac=0.1)     # no game in both
    train_ds = C4Dataset(train, mirror=True)             # torch Dataset, x: 3x6x7, y: result
    test_ds  = C4Dataset(test,  mirror=False)

Network input (proposal 4.2): a 3 x 6 x 7 tensor
    plane 0: stones of the player TO MOVE           (1 = stone, 0 = none)
    plane 1: stones of the opponent
    plane 2: cells that can be played next move     (lowest empty cell of each open column)
  row 0 = BOTTOM row, column 0 = leftmost column, same as Board.to_array().
  Use encode(board) at play time so the network always sees the same layout it was
  trained on (Sriyanth: import it from here in c4/nn/evaluator.py).

Target: the final game result for the player to move, +1 win / 0 draw / -1 loss,
which matches the network's tanh output in (-1, 1).

Splitting is by GAME, not by position, so positions from one game never end up in
both train and test (proposal 4.2). With strict=True (default) a test position is
also dropped if the same position, or its mirror image, occurs anywhere in the
training games. Opening positions repeat across many games, so without this the
test set would contain positions the network has already trained on.

Mirroring: Connect-4 is left-right symmetric, so every training position is also
used flipped (doubles the data). Mirroring is done when a sample is read, so it
costs no extra memory.

Command line summary of a round (games, positions, results, unique positions):
    python -m c4.selfplay.dataset data/selfplay/round_1
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Iterable, Union

import numpy as np

from c4.board import Board, HEIGHT, WIDTH, H1
from c4.selfplay.generate import SHARD_FIELDS

PLANES = 3
_COL_BITS = np.uint64((1 << H1) - 1)
# _SHIFTS[r, c] = bit index of cell (row r, column c)
_SHIFTS = (np.arange(WIDTH)[None, :] * H1 + np.arange(HEIGHT)[:, None]).astype(np.uint64)


# --------------------------------------------------------------------- encoding
def encode_batch(position: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """(N,) position and mask bitboards -> (N, 3, 6, 7) uint8 planes."""
    position = np.asarray(position, dtype=np.uint64)
    mask = np.asarray(mask, dtype=np.uint64)
    own = ((position[:, None, None] >> _SHIFTS) & np.uint64(1)).astype(np.uint8)
    full = ((mask[:, None, None] >> _SHIFTS) & np.uint64(1)).astype(np.uint8)
    heights = full.sum(axis=1)                          # (N, 7) stones per column
    rows = np.arange(HEIGHT)[None, :, None]             # (1, 6, 1)
    playable = (rows == heights[:, None, :]).astype(np.uint8)   # full column: no row matches
    out = np.empty((len(position), PLANES, HEIGHT, WIDTH), dtype=np.uint8)
    out[:, 0] = own
    out[:, 1] = full - own
    out[:, 2] = playable
    return out


def encode(board: Board) -> np.ndarray:
    """One board -> (3, 6, 7) float32, ready for the network."""
    x = encode_batch(np.array([board.position], dtype=np.uint64),
                     np.array([board.mask], dtype=np.uint64))
    return x[0].astype(np.float32)


def mirror_bits(bits: np.ndarray) -> np.ndarray:
    """Left-right mirror of bitboards (vectorised Board.mirrored())."""
    bits = np.asarray(bits, dtype=np.uint64)
    out = np.zeros_like(bits)
    for c in range(WIDTH):
        col = (bits >> np.uint64(c * H1)) & _COL_BITS
        out |= col << np.uint64((WIDTH - 1 - c) * H1)
    return out


def position_keys(position: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Same value as Board.key(): unique per position."""
    return np.asarray(position, dtype=np.uint64) + np.asarray(mask, dtype=np.uint64)


# ------------------------------------------------------------------------ loading
@dataclass
class PositionData:
    """All positions of one or more rounds, as parallel numpy arrays."""
    position: np.ndarray
    mask: np.ndarray
    result: np.ndarray
    game: np.ndarray
    ply: np.ndarray
    move: np.ndarray
    score: np.ndarray
    random: np.ndarray

    def __len__(self) -> int:
        return len(self.result)

    def subset(self, rows) -> "PositionData":
        return PositionData(**{f.name: getattr(self, f.name)[rows] for f in fields(self)})

    def board(self, i: int) -> Board:
        return Board(int(self.position[i]), int(self.mask[i]))

    def num_games(self) -> int:
        return len(np.unique(self.game))


PathLike = Union[str, Path]


def load_positions(round_dirs: Union[PathLike, Iterable[PathLike]]) -> PositionData:
    """Read every finished shard in one or more round folders."""
    if isinstance(round_dirs, (str, Path)):
        round_dirs = [round_dirs]
    parts = {k: [] for k in SHARD_FIELDS}
    for d in round_dirs:
        shards = sorted(Path(d).glob("shard_?????.npz"))
        if not shards:
            raise FileNotFoundError(f"no shard_*.npz files in {d}")
        for path in shards:
            with np.load(path) as z:
                for k in SHARD_FIELDS:
                    parts[k].append(z[k])
    return PositionData(**{k: np.concatenate(v).astype(SHARD_FIELDS[k], copy=False)
                           for k, v in parts.items()})


def split_by_game(data: PositionData, test_frac: float = 0.1, seed: int = 0,
                  strict: bool = True) -> tuple[PositionData, PositionData]:
    """Split whole games into train and test.

    strict=True also removes from the test set every position (or mirror image)
    that appears in a training game, so test positions are truly unseen."""
    if not 0 < test_frac < 1:
        raise ValueError("test_frac must be between 0 and 1")
    games = np.unique(data.game)
    rng = np.random.default_rng(seed)
    n_test = max(1, int(round(len(games) * test_frac)))
    test_games = rng.permutation(games)[:n_test]
    in_test = np.isin(data.game, test_games)
    train, test = data.subset(~in_test), data.subset(in_test)
    if strict and len(test):
        seen = np.concatenate([position_keys(train.position, train.mask),
                               position_keys(mirror_bits(train.position),
                                             mirror_bits(train.mask))])
        unseen = ~np.isin(position_keys(test.position, test.mask), seen)
        test = test.subset(unseen)
    return train, test


# -------------------------------------------------------------------- torch side
def _torch():
    import torch                       # imported here so self-play itself never needs torch
    return torch


class C4Dataset:
    """torch Dataset: item i -> (x float32 [3, 6, 7], y float32 scalar result).

    With mirror=True it has 2 * len(data) items: items len(data).. are the mirror
    images of the first len(data)."""

    def __init__(self, data: PositionData, mirror: bool = False):
        self.planes = encode_batch(data.position, data.mask)       # uint8, compact
        self.targets = data.result.astype(np.float32)
        self.mirror = mirror
        self.n = len(data)

    def __len__(self) -> int:
        return self.n * (2 if self.mirror else 1)

    def __getitem__(self, i: int):
        torch = _torch()
        flip = i >= self.n
        x = self.planes[i - self.n if flip else i]
        if flip:
            x = x[:, :, ::-1]
        return (torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32)),
                torch.tensor(self.targets[i - self.n if flip else i]))

    def tensors(self):
        """Whole dataset as two tensors (X: N x 3 x 6 x 7, y: N), mirrors included.
        Handy for torch.utils.data.TensorDataset when it fits in memory."""
        torch = _torch()
        x, y = self.planes, self.targets
        if self.mirror:
            x = np.concatenate([x, x[:, :, :, ::-1]])
            y = np.concatenate([y, y])
        return (torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32)),
                torch.from_numpy(y.copy()))


def make_datasets(round_dirs, test_frac: float = 0.1, seed: int = 0, strict: bool = True,
                  mirror_train: bool = True):
    """Everything in one call: load, split by game, wrap as torch datasets."""
    train, test = split_by_game(load_positions(round_dirs), test_frac, seed, strict)
    return C4Dataset(train, mirror=mirror_train), C4Dataset(test, mirror=False)


# -------------------------------------------------------------------- summary
def summary(data: PositionData) -> dict:
    keys = position_keys(data.position, data.mask)
    sym = np.minimum(keys, position_keys(mirror_bits(data.position), mirror_bits(data.mask)))
    first = data.ply == 0
    x_res = data.result[first]
    phase = {}
    for name, lo, hi in (("opening (0-9 stones)", 0, 9), ("middle (10-24)", 10, 24),
                         ("late (25-41)", 25, 41)):
        sel = (data.ply >= lo) & (data.ply <= hi)
        phase[name] = int(sel.sum())
    return {
        "games": int(data.num_games()),
        "positions": len(data),
        "unique positions": int(len(np.unique(keys))),
        "unique up to mirroring": int(len(np.unique(sym))),
        "positions after mirroring (training)": 2 * len(data),
        "X wins / O wins / draws": f"{int((x_res == 1).sum())} / {int((x_res == -1).sum())} / "
                                   f"{int((x_res == 0).sum())}",
        "mean game length (moves)": round(len(data) / max(1, data.num_games()), 1),
        "labels +1 / 0 / -1": f"{int((data.result == 1).sum())} / {int((data.result == 0).sum())}"
                              f" / {int((data.result == -1).sum())}",
        "random moves": int(data.random.sum()),
        **{f"positions in {k}": v for k, v in phase.items()},
    }


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Summarise self-play data.")
    p.add_argument("round_dirs", nargs="+")
    p.add_argument("--test-frac", type=float, default=0.1)
    a = p.parse_args(argv)
    data = load_positions(a.round_dirs)
    for k, v in summary(data).items():
        print(f"{k:40s} {v}")
    train, test = split_by_game(data, a.test_frac)
    print(f"{'split (train / unseen test positions)':40s} {len(train)} / {len(test)}")


if __name__ == "__main__":
    main()
