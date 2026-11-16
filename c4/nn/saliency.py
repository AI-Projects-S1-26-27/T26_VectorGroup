"""Occlusion saliency: which stones make the network like a position.   OWNER: Sriyanth

Method (Zeiler & Fergus 2014, "occlusion"): remove one stone at a time, ask the
network again, and record how much the value changed.

    saliency[r, c] = value(board) - value(board with the stone at (r, c) removed)

  > 0  the stone helps the player we are explaining for
  < 0  the stone hurts them
  = 0  empty cell
All occluded boards go through the network in ONE batch (at most 42 + 1 boards).

The stone is removed from the input planes, not from a Board, so a stone in the
middle of a column can be removed (the stones above it would "float"; the
network still gives a value, which is fine for measuring importance, but say so
in the report). Plane 2 (playable cells) is left as in the real position.

Two functions:
  saliency_map(board, evaluator)          -> (6, 7) array, for the PLAYER TO MOVE
                                             (Srikar: the overlay; row 0 = bottom)
  move_saliency(board, col, evaluator, k) -> dict, for the player who PLAYS col
                                             (Naman/Aditya: fallback for quiet moves)
"""
from __future__ import annotations

import numpy as np

from c4.board import Board, HEIGHT, WIDTH
from c4.selfplay.dataset import encode

_default = None


def _evaluator(evaluator):
    """Use the given NNEvaluator, or load the default network once."""
    global _default
    if evaluator is not None:
        return evaluator
    if _default is None:
        from c4.nn.evaluator import NNEvaluator
        _default = NNEvaluator()
    return _default


def saliency_map(board: Board, evaluator=None) -> np.ndarray:
    """(6, 7) float32, row 0 = bottom, from the point of view of the player TO MOVE."""
    ev = _evaluator(evaluator)
    planes = encode(board)
    stones = np.argwhere(planes[0] + planes[1] > 0)            # [(row, col), ...]
    batch = np.repeat(planes[None], len(stones) + 1, axis=0)
    for i, (r, c) in enumerate(stones, start=1):
        batch[i, 0, r, c] = 0.0
        batch[i, 1, r, c] = 0.0
    values = ev.values_from_planes(batch)
    out = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    for i, (r, c) in enumerate(stones, start=1):
        out[r, c] = values[0] - values[i]
    return out


def move_saliency(board: Board, col: int, evaluator=None, k: int = 3) -> dict:
    """Why does the network like the position after `col` is played at `board`?

    Everything is from the point of view of the player who plays `col`
    (the agent, when explaining the agent's move). Returns

      {"value": float in (-1, 1),     network value after the move, for that player
       "cells": [ {"row": r, "col": c,          0-based, row 0 = bottom
                   "owner": "mover" | "opponent",
                   "delta": float}, ... ]}      top k stones by |delta|, biggest first

    delta > 0: the stone makes the position better for the mover
    delta < 0: the stone is a problem for the mover
    If the move ends the game, cells is empty (the rule layer explains wins).
    """
    ev = _evaluator(evaluator)
    after = board.play(col)
    if after.is_over():
        value = 1.0 if after.last_mover_won() else 0.0
        return {"value": value, "cells": []}
    smap = -saliency_map(after, ev)                 # flip to the mover's point of view
    value = -ev.value(after)
    mover_stones = after.position ^ after.mask      # after the move, the mover is NOT to move
    cells = []
    for r in range(HEIGHT):
        for c in range(WIDTH):
            if (after.mask >> (c * (HEIGHT + 1) + r)) & 1:
                owner = "mover" if (mover_stones >> (c * (HEIGHT + 1) + r)) & 1 else "opponent"
                cells.append({"row": r, "col": c, "owner": owner, "delta": float(smap[r, c])})
    cells.sort(key=lambda d: abs(d["delta"]), reverse=True)
    return {"value": float(value), "cells": cells[:k]}
