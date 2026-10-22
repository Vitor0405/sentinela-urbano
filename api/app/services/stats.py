"""Small statistics helpers (no numpy needed for a few dozen sectors)."""

import math
from collections.abc import Sequence


def average_ranks(values: Sequence[float]) -> list[float]:
    """1-based ranks; ties share the mean of the ranks they span."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mean_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = mean_rank
        i = j + 1
    return ranks


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    n = len(xs)
    if n != len(ys) or n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman's rho (Pearson over average ranks). None when undefined."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    return pearson(average_ranks(xs), average_ranks(ys))


def describe_correlation(rho: float | None, n: int) -> str:
    """Plain pt-BR reading of rho for the comparison screen."""
    if rho is None:
        return "Dados insuficientes para medir a concordância (são necessários ao menos 3 setores)."
    strength = abs(rho)
    if strength < 0.2:
        text = "Praticamente não há concordância entre o índice comunitário e o LIRAa"
    else:
        level = "forte" if strength >= 0.7 else "moderada" if strength >= 0.4 else "fraca"
        direction = "positiva" if rho > 0 else "negativa (os índices apontam em sentidos opostos)"
        text = f"Concordância {level} e {direction} entre o índice comunitário e o LIRAa"
    if n < 10:
        text += f"; com apenas {n} setores, interprete com cautela"
    return text + "."
