import random

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from c4.board import Board, HEIGHT, WIDTH
from c4.nn.evaluator import NNEvaluator, to_score
from c4.nn.model import C4Net, count_parameters, load_checkpoint, save_checkpoint
from c4.nn.saliency import move_saliency, saliency_map
from c4.nn.train import train
from c4.search import search
from c4.selfplay.dataset import encode
from c4.selfplay.generate import SelfPlayConfig, run
from c4.trace import MAX_HEURISTIC


class ZeroEvaluator:
    name = "zero"

    def evaluate(self, board):
        return 0


def random_boards(n, seed=1):
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        b = Board.empty()
        for _ in range(rng.randint(0, 30)):
            if b.is_over():
                break
            b = b.play(rng.choice(b.legal_moves()))
        if not b.is_over():
            out.append(b)
    return out


@pytest.fixture(scope="module")
def net():
    torch.manual_seed(0)
    return C4Net().eval()


@pytest.fixture(scope="module")
def ev(net):
    return NNEvaluator(model=net)


# ------------------------------------------------------------------ model
def test_parameter_count_matches_proposal(net):
    assert 140_000 < count_parameters(net) < 170_000


def test_forward_shape_and_range(net):
    x = torch.rand(5, 3, HEIGHT, WIDTH)
    y = net(x)
    assert y.shape == (5,)
    assert torch.all(y > -1) and torch.all(y < 1)


def test_checkpoint_round_trip(net, tmp_path):
    save_checkpoint(net, tmp_path / "m.pt", info={"note": "test"})
    m2, info = load_checkpoint(tmp_path / "m.pt")
    x = torch.rand(3, 3, HEIGHT, WIDTH)
    assert torch.allclose(net(x), m2(x))
    assert info["note"] == "test"


# ------------------------------------------------------------------ evaluator
def test_missing_weights_gives_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        NNEvaluator(tmp_path / "nope.pt")


def test_load_from_file(net, tmp_path):
    save_checkpoint(net, tmp_path / "m.pt")
    ev2 = NNEvaluator.load(tmp_path / "m.pt")
    b = Board.from_moves("4453")
    assert ev2.name == "network"
    assert ev2.evaluate(b) == NNEvaluator(model=net).evaluate(b)


def test_evaluate_is_int_in_range(ev):
    for b in random_boards(20):
        s = ev.evaluate(b)
        assert isinstance(s, int) and -MAX_HEURISTIC <= s <= MAX_HEURISTIC


def test_to_score_clamps():
    assert to_score(0.5) == 500
    assert to_score(50.0) == MAX_HEURISTIC


def test_cache_avoids_second_network_call(net):
    e = NNEvaluator(model=net)
    b = Board.from_moves("44")
    e.evaluate(b)
    n = e.net_evals
    e.evaluate(b)
    assert e.net_evals == n


def test_batch_matches_single(net):
    boards = random_boards(10, seed=3)
    single = [NNEvaluator(model=net).evaluate(b) for b in boards]
    assert NNEvaluator(model=net).evaluate_batch(boards) == single


def test_search_runs_with_network(ev):
    trace = search(Board.from_moves("4444"), ev, time_limit=0.3, max_depth=3)
    assert trace.evaluator == "network"
    assert trace.chosen in Board.from_moves("4444").legal_moves()


# ------------------------------------------------------------------ saliency
def test_saliency_zero_on_empty_cells(ev):
    b = Board.from_moves("4453")
    smap = saliency_map(b, ev)
    assert smap.shape == (HEIGHT, WIDTH)
    empty = encode(b)[:2].sum(axis=0) == 0
    assert np.all(smap[empty] == 0)


def test_move_saliency_format(ev):
    b = Board.from_moves("4453")
    out = move_saliency(b, 3, ev, k=3)
    assert -1 < out["value"] < 1
    assert len(out["cells"]) == 3
    for cell in out["cells"]:
        assert set(cell) == {"row", "col", "owner", "delta"}
        assert cell["owner"] in ("mover", "opponent")
    deltas = [abs(c["delta"]) for c in out["cells"]]
    assert deltas == sorted(deltas, reverse=True)


def test_move_saliency_winning_move(ev):
    b = Board.from_moves("141414")          # X wins by playing column 1 (index 0)
    out = move_saliency(b, 0, ev)
    assert out == {"value": 1.0, "cells": []}


# ------------------------------------------------------------------ training
def test_training_end_to_end(tmp_path):
    cfg = SelfPlayConfig(games=30, round=0, evaluator=f"{__name__}:ZeroEvaluator", depth=1,
                         games_per_shard=10, out_dir=str(tmp_path / "sp"), workers=1)
    run(cfg, quiet=True)
    out = tmp_path / "models" / "t.pt"
    report = train([cfg.round_dir()], out, epochs=2, batch_size=64,
                   results_dir=tmp_path / "res", log=lambda *a: None)
    assert out.exists() and (out.parent / "nn_latest.pt").exists()
    assert len(report["history"]) >= 1
    e = NNEvaluator(out)
    assert isinstance(e.evaluate(Board.from_moves("44")), int)
