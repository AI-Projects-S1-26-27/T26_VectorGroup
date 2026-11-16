"""Small statistics helpers shared by the eval scripts.            OWNER: Mani"""
from __future__ import annotations

import math
import random


def wilson(successes: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion (successes may be a half-integer
    when draws count 0.5)."""
    if n <= 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_mean_ci(values, n_boot: int = 2000, seed: int = 0,
                      alpha: float = 0.05) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean of `values` (resamples the items)."""
    values = list(values)
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    return (means[int(alpha / 2 * n_boot)], means[int((1 - alpha / 2) * n_boot) - 1])


def sign_flip_pvalue(diffs, n_perm: int = 10000, seed: int = 0) -> float:
    """Two-sided paired sign-flip permutation test: is the mean difference zero?"""
    diffs = [d for d in diffs]
    if not diffs:
        return float("nan")
    rng = random.Random(seed)
    observed = abs(sum(diffs))
    hits = 0
    for _ in range(n_perm):
        if abs(sum(d if rng.random() < 0.5 else -d for d in diffs)) >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (n_perm + 1)
