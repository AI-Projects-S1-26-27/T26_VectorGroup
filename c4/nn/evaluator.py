"""NNEvaluator: the network plugged into the search.          OWNER: Sriyanth

Follows the Evaluator protocol in c4/evaluator.py, so it is a drop-in
replacement for HeuristicEvaluator:

    ev = NNEvaluator()                      # loads models/nn_latest.pt
    ev = NNEvaluator("models/round1.pt")    # or a specific file
    ev.evaluate(board)  -> int in [-MAX_HEURISTIC, MAX_HEURISTIC], player to move
    ev.value(board)     -> float in (-1, 1), the raw network output

Used by
  * web/app.py               NNEvaluator()                 (Srikar)
  * c4/selfplay/generate.py  NNEvaluator.load(path)        (Veer, round 2)
  * eval/ scripts            value() / evaluate()          (Mani)

Speed: one network call costs much more than the hand-written function, so
  * every result is cached by Board.key() (positions repeat a lot inside a search),
  * evaluate_batch(boards) scores many boards in ONE forward pass. The search can
    use it to score all children of a depth-1 node together (see note to Shridali).
  * torch uses one thread: for a single 6x7 board, thread start-up costs more than
    it saves.
The fair comparison with the heuristic is at equal TIME per move (proposal 4.2).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import numpy as np
import torch

from c4.board import Board
from c4.nn.model import C4Net, load_checkpoint
from c4.selfplay.dataset import encode, encode_batch
from c4.trace import MAX_HEURISTIC, NN_SCALE

REPO_ROOT = Path(__file__).resolve().parents[2]
# override with the environment variable C4_MODEL=path/to/weights.pt
DEFAULT_MODEL = Path(os.environ.get("C4_MODEL", REPO_ROOT / "models" / "nn_latest.pt"))


def to_score(value: float) -> int:
    """Network value in (-1, 1) -> integer score on the search's scale (trace.py)."""
    return max(-MAX_HEURISTIC, min(MAX_HEURISTIC, int(round(float(value) * NN_SCALE))))


class NNEvaluator:
    name = "network"

    def __init__(self, model_path=None, *, model: C4Net | None = None,
                 cache_size: int = 500_000):
        torch.set_num_threads(1)
        self.info: dict = {}
        if model is None:
            path = Path(model_path) if model_path else DEFAULT_MODEL
            if not path.exists():
                raise FileNotFoundError(
                    f"network weights not found at {path}. Train them with "
                    f"'python -m c4.nn.train ...' or copy the shared nn_latest.pt into models/")
            model, self.info = load_checkpoint(path)
            self.info["path"] = str(path)
        self.model = model.eval()
        self.cache: dict[int, float] = {}
        self.cache_size = cache_size
        self.calls = 0          # evaluate()/value() calls
        self.net_evals = 0      # boards actually sent through the network

    @classmethod
    def load(cls, path) -> "NNEvaluator":
        """Used by c4/selfplay/generate.py for round 2+."""
        return cls(path)

    # ------------------------------------------------------------ raw network
    def values_from_planes(self, planes: np.ndarray) -> np.ndarray:
        """(N, 3, 6, 7) encoded planes -> (N,) float values in (-1, 1). No cache."""
        x = torch.from_numpy(np.ascontiguousarray(planes, dtype=np.float32))
        with torch.inference_mode():
            out = self.model(x).numpy()
        self.net_evals += len(out)
        return out

    def _remember(self, key: int, v: float) -> None:
        if len(self.cache) >= self.cache_size:
            self.cache.clear()
        self.cache[key] = v

    # ------------------------------------------------------------ public API
    def value(self, board: Board) -> float:
        """Raw network output for the player to move, in (-1, 1)."""
        self.calls += 1
        key = board.key()
        v = self.cache.get(key)
        if v is None:
            v = float(self.values_from_planes(encode(board)[None])[0])
            self._remember(key, v)
        return v

    def evaluate(self, board: Board) -> int:
        """Evaluator protocol: integer score for the player to move."""
        return to_score(self.value(board))

    def values_batch(self, boards: Iterable[Board]) -> list[float]:
        boards = list(boards)
        self.calls += len(boards)
        keys = [b.key() for b in boards]
        missing = [i for i, k in enumerate(keys) if k not in self.cache]
        if missing:
            pos = np.array([boards[i].position for i in missing], dtype=np.uint64)
            msk = np.array([boards[i].mask for i in missing], dtype=np.uint64)
            for i, v in zip(missing, self.values_from_planes(encode_batch(pos, msk))):
                self._remember(keys[i], float(v))
        return [self.cache[k] for k in keys]

    def evaluate_batch(self, boards: Iterable[Board]) -> list[int]:
        """Scores for many boards with one forward pass (same numbers as evaluate())."""
        return [to_score(v) for v in self.values_batch(boards)]

    def clear_cache(self) -> None:
        self.cache.clear()
