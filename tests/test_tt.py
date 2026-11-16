import pytest

from c4.search import EXACT, LOWER, UPPER
from c4.tt import TranspositionTable


@pytest.mark.parametrize("flag", [EXACT, LOWER, UPPER])
def test_round_trip(flag):
    tt = TranspositionTable()
    assert tt.probe(7) is None
    tt.store(7, 4, -123, flag, 0)
    assert tt.probe(7) == (4, -123, flag, 0)
    assert tt.stats() == dict(entries=1, probes=2, hits=1, stores=1)


def test_replacement_prefers_depth_then_exact():
    tt = TranspositionTable()
    tt.store(1, 4, 12, EXACT, 3)
    tt.store(1, 3, 99, EXACT, 2)
    tt.store(1, 4, 99, LOWER, 2)
    assert tt.probe(1) == (4, 12, EXACT, 3)
    tt.store(1, 5, 99, UPPER, None)
    assert tt.probe(1) == (5, 99, UPPER, None)
    tt.store(1, 5, 42, EXACT, 0)
    assert tt.probe(1) == (5, 42, EXACT, 0)


def test_capacity_and_clear():
    tt = TranspositionTable(max_entries=2)
    for key in range(3):
        tt.store(key, 1, 0, EXACT, None)
    assert len(tt) == 2
    assert tt.probe(0) is None
    assert tt.probe(2) == (1, 0, EXACT, None)
    tt.clear()
    assert tt.stats() == dict(entries=0, probes=0, hits=0, stores=0)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        TranspositionTable(0)
    with pytest.raises(ValueError):
        TranspositionTable().store(0, 1, 0, 42, None)
