"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations
from math import comb
from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have equal lengths")

    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}

    for h, j in zip(human, judge):
        if h not in ("PASS", "FAIL") or j not in ("PASS", "FAIL"):
            raise ValueError("Labels must be PASS or FAIL")

        if h == POS and j == POS:
            counts["tp"] += 1
        elif h != POS and j == POS:
            counts["fp"] += 1
        elif h == POS and j != POS:
            counts["fn"] += 1
        else:
            counts["tn"] += 1

    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    counts = confusion(human, judge)

    tp = counts["tp"]
    fp = counts["fp"]
    fn = counts["fn"]

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    counts = confusion(human, judge)

    tp = counts["tp"]
    fp = counts["fp"]
    fn = counts["fn"]
    tn = counts["tn"]

    n = tp + fp + fn + tn
    if n == 0:
        raise ValueError("Kappa undefined for empty input")

    p_o = (tp + tn) / n

    human_positive = (tp + fn) / n
    judge_positive = (tp + fp) / n

    human_negative = (tn + fp) / n
    judge_negative = (tn + fn) / n

    p_e = (
        human_positive * judge_positive
        + human_negative * judge_negative
    )

    if abs(1.0 - p_e) < 1e-12:
        raise ValueError("Kappa undefined when expected agreement is 1")

    return (p_o - p_e) / (1.0 - p_e)


def rogan_gladen(
    observed_rate: float,
    sensitivity: float,
    specificity: float
) -> float:
    """Correct observed failure rate for judge error; clip to [0, 1]."""

    for value in (observed_rate, sensitivity, specificity):
        if not 0.0 <= value <= 1.0:
            raise ValueError("Rates must be between 0 and 1")

    denominator = sensitivity + specificity - 1.0

    if abs(denominator) < 1e-12:
        raise ValueError("Rogan-Gladen undefined: sensitivity + specificity = 1")

    corrected = (observed_rate + specificity - 1.0) / denominator

    return max(0.0, min(1.0, corrected))


def paired_bootstrap(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_resamples: int = 1000,
    rng: int = 2027,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    """Paired percentile bootstrap of per-item means."""
    import numpy as np
    from scipy.stats import bootstrap

    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)

    if x.ndim != 1 or y.ndim != 1:
        raise ValueError("Inputs must be one-dimensional")
    if len(x) != len(y) or len(x) == 0:
        raise ValueError("Inputs must have equal nonzero lengths")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("Inputs must contain finite values")
    if n_resamples <= 0:
        raise ValueError("n_resamples must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")

    delta = float(np.mean(x - y))

    if np.array_equal(x, y):
        return 0.0, 0.0, 0.0

    if len(x) < 2:
        raise ValueError("At least two paired items required")

    result = bootstrap(
        (x, y),
        statistic=lambda aa, bb: np.mean(aa - bb),
        paired=True,
        n_resamples=n_resamples,
        confidence_level=confidence,
        method="percentile",
        rng=np.random.default_rng(rng),
    )

    return (
        delta,
        float(result.confidence_interval.low),
        float(result.confidence_interval.high),
    )



def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that at least one of k trials passes."""
    if not all(type(x) is int for x in (n, c, k)):
        raise ValueError("n, c, k must be integers")
    if n <= 0 or not (0 <= c <= n) or not (1 <= k <= n):
        raise ValueError("Require n > 0, 0 <= c <= n, 1 <= k <= n")

    if n - c < k:
        return 1.0

    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """Probability that all k trials pass (pass^k)."""
    if not all(type(x) is int for x in (n, c, k)):
        raise ValueError("n, c, k must be integers")
    if n <= 0 or not (0 <= c <= n) or not (1 <= k <= n):
        raise ValueError("Require n > 0, 0 <= c <= n, 1 <= k <= n")

    if c < k:
        return 0.0

    return comb(c, k) / comb(n, k)
