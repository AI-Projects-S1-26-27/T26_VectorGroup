
"""Move ordering for Connect-4 alpha-beta search."""

from c4.board import Board, WIDTH


def move_ordering(
    board: Board,
    moves: list[int],
    tt_move: int | None = None,
) -> list[int]:
    """Return the same moves, ordered best-first.

    Priorities:
      1. Transposition-table best move
      2. Immediate winning moves
      3. Moves blocking an immediate opponent win
      4. Centre-first positional ordering

    Does not modify the input list.
    """

    if not moves:
        return []

    # Detect immediate winning moves for the player to move.
    winning = set(board.winning_moves())

    # Identify opponent's current immediate winning cells.
    opponent_bits = board.mask ^ board.position
    opponent_board = Board(opponent_bits, board.mask)
    opponent_winning = set(opponent_board.winning_moves())

    centre = WIDTH // 2

    def priority(col: int):
        if col == tt_move:
            category = 0
        elif col in winning:
            category = 1
        elif col in opponent_winning:
            category = 2
        else:
            category = 3

        return (category, abs(col - centre), col)

    return sorted(moves, key=priority)
