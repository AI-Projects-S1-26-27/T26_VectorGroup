import random

import numpy as np
import pytest

from c4.board import Board, HEIGHT, WIDTH
from c4.selfplay.dataset import (C4Dataset, encode, encode_batch, load_positions, make_datasets,
                                 mirror_bits, position_keys, split_by_game, summary)
from c4.selfplay.generate import SelfPlayConfig, run


class ZeroEvaluator:
    name = "zero"

    def evaluate(self, board):
        return 0


def random_boards(n, seed=1):
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        b = Board.empty()
        for _ in range(rng.randint(0, 41)):
            if b.is_over():
                break
            b = b.play(rng.choice(b.legal_moves()))
        if not b.is_over():
            out.append(b)
    return out


@pytest.fixture(scope="module")
def round_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("selfplay")
    c = SelfPlayConfig(games=40, round=0, evaluator=f"{__name__}:ZeroEvaluator", depth=2,
                       games_per_shard=10, out_dir=str(out), workers=1)
    run(c, quiet=True)
    return c.round_dir()


def test_encode_matches_board():
    for b in random_boards(50):
        x = encode(b)
        assert x.shape == (3, HEIGHT, WIDTH) and x.dtype == np.float32
        arr = b.to_array()
        assert np.array_equal(x[0], (arr == 1).astype(np.float32))
        assert np.array_equal(x[1], (arr == -1).astype(np.float32))
        for c in range(WIDTH):
            col = x[2][:, c]
            if b.can_play(c):
                assert col.sum() == 1 and col[b.height(c)] == 1
            else:
                assert col.sum() == 0


def test_encode_batch_equals_single():
    boards = random_boards(20, seed=2)
    xb = encode_batch(np.array([b.position for b in boards], dtype=np.uint64),
                      np.array([b.mask for b in boards], dtype=np.uint64))
    for b, x in zip(boards, xb):
        assert np.array_equal(x.astype(np.float32), encode(b))


def test_mirror_bits_matches_board():
    boards = random_boards(30, seed=3)
    pos = np.array([b.position for b in boards], dtype=np.uint64)
    mask = np.array([b.mask for b in boards], dtype=np.uint64)
    for b, p, m in zip(boards, mirror_bits(pos), mirror_bits(mask)):
        assert Board(int(p), int(m)) == b.mirrored()
    assert np.array_equal(position_keys(pos, mask), [b.key() for b in boards])


def test_load_and_summary(round_dir):
    data = load_positions(round_dir)
    assert data.num_games() == 40
    assert set(np.unique(data.result)) <= {-1, 0, 1}
    s = summary(data)
    assert s["games"] == 40 and s["positions"] == len(data)
    assert data.board(0).num_moves == data.ply[0]


def test_split_is_by_game_and_strict(round_dir):
    data = load_positions(round_dir)
    train, test = split_by_game(data, test_frac=0.25, seed=0, strict=False)
    assert len(train) + len(test) == len(data)
    assert not set(train.game) & set(test.game)
    _, strict_test = split_by_game(data, test_frac=0.25, seed=0, strict=True)
    seen = set(position_keys(train.position, train.mask).tolist())
    seen |= set(position_keys(mirror_bits(train.position), mirror_bits(train.mask)).tolist())
    assert 0 < len(strict_test) < len(test)             # empty-board etc. are removed
    assert not set(position_keys(strict_test.position, strict_test.mask).tolist()) & seen


def test_torch_dataset_with_mirroring(round_dir):
    torch = pytest.importorskip("torch")
    data = load_positions(round_dir)
    ds = C4Dataset(data, mirror=True)
    assert len(ds) == 2 * len(data)
    i = 25
    x, y = ds[i]
    xm, ym = ds[len(data) + i]
    assert x.dtype == torch.float32 and x.shape == (3, 6, 7)
    assert float(y) == float(ym) == float(data.result[i])
    assert np.array_equal(xm.numpy(), encode(data.board(i).mirrored()))
    X, Y = ds.tensors()
    assert X.shape == (2 * len(data), 3, 6, 7) and Y.shape == (2 * len(data),)
    assert torch.equal(X[len(data) + i], xm)


def test_make_datasets(round_dir):
    pytest.importorskip("torch")
    train, test = make_datasets(round_dir, test_frac=0.2)
    assert len(train) % 2 == 0 and len(test) > 0
