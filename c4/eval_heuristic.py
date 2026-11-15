"""Bounded, symmetric Connect-4 features from the mover's perspective."""
from c4.board import Board, HEIGHT, WIDTH, H1
from c4.trace import MAX_HEURISTIC


def _windows():
    for col in range(WIDTH):
        for row in range(HEIGHT):
            for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
                if 0 <= col + 3 * dc < WIDTH and 0 <= row + 3 * dr < HEIGHT:
                    yield sum(1 << ((col + i * dc) * H1 + row + i * dr)
                              for i in range(4))


WINDOWS = tuple(_windows())
WEIGHTS = (0, 1, 10, 50, 500)
CENTER_MASK = ((1 << HEIGHT) - 1) << ((WIDTH // 2) * H1)


class HeuristicEvaluator:
    """Reward centre control, open lines, and gravity-playable threats.

    Blocked lines score zero. Features are subtracted symmetrically so swapping
    the mover negates the score. Proven outcomes remain the searcher's job.
    """
    name = "heuristic"

    def evaluate(self, board: Board) -> int:
        own, opponent = board.position, board.position ^ board.mask
        score = 3 * ((own & CENTER_MASK).bit_count()
                     - (opponent & CENTER_MASK).bit_count())
        for window in WINDOWS:
            us = (own & window).bit_count()
            them = (opponent & window).bit_count()
            if not them:
                score += WEIGHTS[us]
            if not us:
                score -= WEIGHTS[them]
        other = Board(opponent, board.mask)
        score += 200 * (len(board.winning_moves()) - len(other.winning_moves()))
        return max(-MAX_HEURISTIC, min(MAX_HEURISTIC, score))
