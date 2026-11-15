"""Connect-4 board as a pair of bitboards.           

Every other module talks to the game through this class, so keep the public API
stable.

Bit layout (Pascal Pons style, http://blog.gamesolver.org/):
  * 7 columns; each column uses 7 bits = 6 playable cells + 1 sentinel bit that is
    always 0, so the whole board fits in 49 bits.
  * column c occupies bits [7c, 7c+6]; bit 7c is the BOTTOM cell of column c.
  * `position` = stones of the player TO MOVE,  `mask` = stones of BOTH players.
  * Board objects are immutable: play() returns a new Board.

Conventions used everywhere in the project:
  * columns are 0..6 in code (1..7 for humans),  rows are 0..5 with row 0 = BOTTOM.
  * player 0 = first player (drawn as X), player 1 = second player (drawn as O).
"""
from __future__ import annotations

import numpy as np

WIDTH = 7
HEIGHT = 6
H1 = HEIGHT + 1          # bits per column (6 cells + sentinel)
SIZE = WIDTH * HEIGHT    # 42
CENTER_FIRST = (3, 2, 4, 1, 5, 0, 6)   # default move order


def _col_mask(col: int) -> int:
    return ((1 << HEIGHT) - 1) << (col * H1)


def _bottom_bit(col: int) -> int:
    return 1 << (col * H1)


def _top_bit(col: int) -> int:
    return 1 << (HEIGHT - 1 + col * H1)


BOTTOM_MASK = sum(_bottom_bit(c) for c in range(WIDTH))
BOARD_MASK = sum(_col_mask(c) for c in range(WIDTH))


def has_alignment(bits: int) -> bool:
    """True if the stones in `bits` contain four in a row (any direction)."""
    # horizontal
    m = bits & (bits >> H1)
    if m & (m >> (2 * H1)):
        return True
    # diagonal  /
    m = bits & (bits >> HEIGHT)
    if m & (m >> (2 * HEIGHT)):
        return True
    # diagonal  \
    m = bits & (bits >> (HEIGHT + 2))
    if m & (m >> (2 * (HEIGHT + 2))):
        return True
    # vertical
    m = bits & (bits >> 1)
    if m & (m >> 2):
        return True
    return False


class Board:
    __slots__ = ("position", "mask")

    def __init__(self, position: int = 0, mask: int = 0):
        self.position = position
        self.mask = mask

    # ------------------------------------------------------------------ build
    @classmethod
    def empty(cls) -> "Board":
        return cls(0, 0)

    @classmethod
    def from_moves(cls, moves: str) -> "Board":
        """Build a board from a string of 1-indexed columns, e.g. "4453"."""
        b = cls.empty()
        for ch in moves:
            col = int(ch) - 1
            if not (0 <= col < WIDTH) or b.is_over() or not b.can_play(col):
                raise ValueError(f"illegal move {ch!r} in sequence {moves!r}")
            b = b.play_unchecked(col)
        return b

    @classmethod
    def from_absolute(cls, arr) -> "Board":
        """Inverse of to_absolute(): arr is 6x7, row 0 = bottom,
        +1 = first player, -1 = second player, 0 = empty."""
        p1 = p2 = 0
        for c in range(WIDTH):
            for r in range(HEIGHT):
                v = int(arr[r][c])
                bit = 1 << (c * H1 + r)
                if v == 1:
                    p1 |= bit
                elif v == -1:
                    p2 |= bit
        n1, n2 = p1.bit_count(), p2.bit_count()
        if n1 == n2:
            position = p1            # first player to move
        elif n1 == n2 + 1:
            position = p2            # second player to move
        else:
            raise ValueError("stone counts are impossible for a real game")
        mask = p1 | p2
        for c in range(WIDTH):
            col = (mask >> (c * H1)) & ((1 << H1) - 1)
            if col & (col + 1):
                raise ValueError("floating stone: column is not gravity-consistent")
        return cls(position, mask)

    # ------------------------------------------------------------------ state
    @property
    def num_moves(self) -> int:
        return self.mask.bit_count()

    @property
    def player_to_move(self) -> int:
        """0 = first player (X), 1 = second player (O)."""
        return self.num_moves & 1

    def height(self, col: int) -> int:
        """Number of stones in a column (0..6). Next stone lands on row height(col)."""
        return (self.mask & _col_mask(col)).bit_count()

    def can_play(self, col: int) -> bool:
        return (self.mask & _top_bit(col)) == 0

    def legal_moves(self) -> list[int]:
        """Playable columns in natural order 0..6 (ordering is search's job)."""
        return [c for c in range(WIDTH) if (self.mask & _top_bit(c)) == 0]

    def key(self) -> int:
        """Unique integer for this position (use as transposition-table key)."""
        return self.position + self.mask

    # ------------------------------------------------------------------ moves
    def play(self, col: int) -> "Board":
        if not (0 <= col < WIDTH) or not self.can_play(col):
            raise ValueError(f"column {col} is not playable")
        return self.play_unchecked(col)

    def play_unchecked(self, col: int) -> "Board":
        """Fast path for search: caller guarantees col is playable."""
        return Board(self.position ^ self.mask,
                     self.mask | (self.mask + _bottom_bit(col)))

    def wins_by_playing(self, col: int) -> bool:
        """Would the player to move win immediately by playing `col`?"""
        new_bit = (self.mask + _bottom_bit(col)) & _col_mask(col)
        return has_alignment(self.position | new_bit)

    def winning_moves(self) -> list[int]:
        return [c for c in self.legal_moves() if self.wins_by_playing(c)]

    # --------------------------------------------------------------- terminal
    def last_mover_won(self) -> bool:
        """True if the player who just moved has four in a row."""
        return has_alignment(self.position ^ self.mask)

    def is_draw(self) -> bool:
        return self.num_moves == SIZE and not self.last_mover_won()

    def is_over(self) -> bool:
        return self.last_mover_won() or self.num_moves == SIZE

    # ---------------------------------------------------------------- exports
    def to_array(self) -> np.ndarray:
        """6x7 int8, row 0 = bottom. +1 = player to move, -1 = opponent, 0 = empty."""
        arr = np.zeros((HEIGHT, WIDTH), dtype=np.int8)
        for c in range(WIDTH):
            for r in range(HEIGHT):
                bit = 1 << (c * H1 + r)
                if self.position & bit:
                    arr[r, c] = 1
                elif self.mask & bit:
                    arr[r, c] = -1
        return arr

    def to_absolute(self) -> np.ndarray:
        """6x7 int8, row 0 = bottom. +1 = first player (X), -1 = second (O)."""
        sign = 1 if self.num_moves % 2 == 0 else -1
        return (self.to_array() * sign).astype(np.int8)

    def mirrored(self) -> "Board":
        """Left-right mirror image (for data augmentation / symmetric TT keys)."""
        def mir(bits: int) -> int:
            out = 0
            for c in range(WIDTH):
                out |= ((bits >> (c * H1)) & ((1 << H1) - 1)) << ((WIDTH - 1 - c) * H1)
            return out
        return Board(mir(self.position), mir(self.mask))

    def render(self) -> str:
        sym = {1: "X", -1: "O", 0: "."}
        arr = self.to_absolute()
        rows = [" ".join(sym[int(arr[r, c])] for c in range(WIDTH))
                for r in reversed(range(HEIGHT))]
        rows.append("1 2 3 4 5 6 7")
        return "\n".join(rows)

    # ------------------------------------------------------------------ dunder
    def __eq__(self, other) -> bool:
        return (isinstance(other, Board)
                and self.position == other.position and self.mask == other.mask)

    def __hash__(self) -> int:
        return hash((self.position, self.mask))

    def __repr__(self) -> str:
        return f"Board(moves={self.num_moves}, key={self.key()})"