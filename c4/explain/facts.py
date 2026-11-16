"""Basic board facts the explanation rules are built on.      OWNER: Naman

Works on a plain 6x7 array (board.to_array(): row 0 = bottom, +1 = one side,
-1 = the other, 0 = empty), not on bitboards, so the rules stay easy to read and
check by hand.

Facts:
  * LINES            the 69 possible lines of four, as tuples of (row, col)
  * line_facts       for each line: how many stones each side has, which cells are empty
  * playable_cells   the empty cells a stone can be dropped into right now
  * threat_cells     empty cells that would complete four for one side
  * is_odd_row       odd/even parity of a row, counted the human way (bottom row = 1)
"""
from __future__ import annotations

from c4.board import Board, HEIGHT, WIDTH


def _lines():
    for r in range(HEIGHT):
        for c in range(WIDTH):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (-1, 1)):   # -, |, /, \
                if 0 <= r + 3 * dr < HEIGHT and 0 <= c + 3 * dc < WIDTH:
                    yield tuple((r + i * dr, c + i * dc) for i in range(4))


LINES = tuple(_lines())
assert len(LINES) == 69          # 24 horizontal + 21 vertical + 12 + 12 diagonal


def line_facts(arr, who: int = 1) -> list[tuple[tuple, int, int, list]]:
    """For every line: (line, stones of `who`, stones of the other side, empty cells)."""
    out = []
    for line in LINES:
        vals = [int(arr[r][c]) for r, c in line]
        out.append((line, vals.count(who), vals.count(-who),
                    [cell for cell, v in zip(line, vals) if v == 0]))
    return out


def playable_cells(board: Board) -> set[tuple[int, int]]:
    """Empty cells a stone would land in if dropped now, as (row, col)."""
    return {(board.height(c), c) for c in board.legal_moves()}


def threat_cells(arr, who: int) -> dict[tuple[int, int], tuple]:
    """Empty cells where a stone of `who` would make four in a row (gravity ignored).
    Maps each cell to one line it would complete."""
    out = {}
    for line, mine, theirs, empty in line_facts(arr, who):
        if mine == 3 and theirs == 0:
            out.setdefault(empty[0], line)
    return out


def is_odd_row(row: int) -> bool:
    """Row 0 (bottom) is row 1 for humans, so it is odd. Odd threats favour the
    first player, even threats the second (Allis 1988)."""
    return row % 2 == 0
