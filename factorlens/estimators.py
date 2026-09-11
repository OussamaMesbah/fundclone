"""Estimators that turn a trailing window of returns into clone weights.

Each follows replication.Estimator: estimate(y, X, previous, config) receives the fund's
excess returns y (length T), those of the available ETFs X (T x N) and the weights set
at the last rebalance, and returns N weights with w >= 0 and sum(w) <= 1.

The default, stable_least_squares, builds on an out-of-sample comparison of seven
approaches (exponential weighting, ridge penalties, greedy selection, Kalman filtering,
window ensembles and more; see benchmarks/), each tuned on 21 funds and checked on 20
others. Their median tracking errors differed by at most 0.15 percentage points, so the
choice rests on turnover, stability and simplicity: with a 2% minimum position, this one
trades about half as much as plain least squares for about the same tracking error.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import nnls

from factorlens.replication import Estimator, ReplicationConfig, constrained_least_squares

HALF_LIFE_DAYS = 63  # recent days count more: an observation's weight halves every 63 days
STABILITY = 0.1  # pull towards last month's weights, in units of the average ETF variance
STICKINESS = 0.25  # forward selection favours ETFs already held by this share of the gain
SCREEN = 8  # candidates refitted per step of forward selection
_BUDGET_ROW = 1e3  # weight of the sum(w) + cash = 1 row in the least-squares system


def _system(y: np.ndarray, X: np.ndarray, config: ReplicationConfig):
    """Rows scaled by recency weights and by the average ETF variance, so that the
    squared residual of the scaled system is a recency-weighted mean squared error in
    units of that variance.

    With `config.overlap` > 1, daily rows are first summed over overlapping blocks of
    that many days: multi-day returns absorb prices set at different times of day while
    keeping almost as many rows as the window has days.
    """
    days_per_row = max(1.0, config.window / len(y))  # weekly fits see about window / 5 rows
    if config.overlap > 1 and days_per_row == 1.0 and len(y) > config.overlap:
        y, X = _overlapping_sums(y, config.overlap), _overlapping_sums(X, config.overlap)
    T = len(y)
    recency = 0.5 ** (np.arange(T)[::-1] * days_per_row / HALF_LIFE_DAYS)
    recency /= recency.mean()
    unit = float(np.mean(np.einsum("ij,ij->j", X, X)) / T) or 1.0
    root = np.sqrt(recency / (T * unit))
    return X * root[:, None], y * root


def _overlapping_sums(values: np.ndarray, days: int) -> np.ndarray:
    """Sums over every run of `days` consecutive rows (T - days + 1 rows)."""
    total = np.cumsum(values, axis=0)
    head = np.zeros((1, *values.shape[1:]))
    total = np.concatenate([head, total])
    return total[days:] - total[:-days]


def _solve(A: np.ndarray, b: np.ndarray, penalty: float, anchor: np.ndarray) -> np.ndarray:
    """min ||b - A w||^2 + penalty * ||w - anchor||^2 subject to w >= 0, sum(w) <= 1.

    One non-negative least-squares problem: the penalty becomes extra rows, cash a slack
    column, and sum(w) + cash = 1 a heavily weighted row.
    """
    rows, n = A.shape
    blocks, rhs = [np.hstack([A, np.zeros((rows, 1))])], [b]
    if penalty > 0:
        root = np.sqrt(penalty)
        blocks.append(np.hstack([root * np.eye(n), np.zeros((n, 1))]))
        rhs.append(root * anchor)
    blocks.append(np.full((1, n + 1), _BUDGET_ROW))
    rhs.append(np.array([_BUDGET_ROW]))
    z, _ = nnls(np.vstack(blocks), np.concatenate(rhs), maxiter=50 * (n + 1))
    w = np.clip(z[:n], 0.0, None)
    return w / w.sum() if w.sum() > 1.0 else w


def _fit(A: np.ndarray, b: np.ndarray, previous: np.ndarray, columns: np.ndarray) -> np.ndarray:
    penalty = STABILITY if previous.sum() > 1e-12 else 0.0
    w = np.zeros(A.shape[1])
    w[columns] = _solve(A[:, columns], b, penalty, previous[columns])
    return w


def _trim(
    A: np.ndarray, b: np.ndarray, previous: np.ndarray, w: np.ndarray, min_weight: float
) -> np.ndarray:
    """Drop positions below `min_weight` and refit the rest, up to three times. If no
    position reaches the minimum, the clone holds only cash."""
    for _ in range(3):
        keep = np.flatnonzero((w > 0) & (w >= min_weight))
        if len(keep) == np.count_nonzero(w > 0):
            return w
        if not len(keep):
            return np.zeros_like(w)
        w = _fit(A, b, previous, keep)
    w[w < min_weight] = 0.0
    return w


def stable_least_squares(
    y: np.ndarray, X: np.ndarray, previous: np.ndarray, config: ReplicationConfig
) -> np.ndarray:
    """Recency-weighted least squares with a pull towards last month's weights.

    Observations are weighted with a 63-trading-day half-life, so the clone follows style
    drift. The penalty keeps weights the data cannot tell apart, such as those of highly
    correlated ETFs, where they were last month, which cuts turnover. Positions below
    `config.min_weight` are then dropped and the rest refitted, so the clone has no
    holdings too small to matter.
    """
    A, b = _system(np.asarray(y, float), np.asarray(X, float), config)
    previous = np.asarray(previous, float)
    w = _fit(A, b, previous, np.arange(A.shape[1]))
    return _trim(A, b, previous, w, config.min_weight)


def forward_selection(
    y: np.ndarray, X: np.ndarray, previous: np.ndarray, config: ReplicationConfig
) -> np.ndarray:
    """At most `config.max_etfs` ETFs, added one at a time.

    Each step refits the stable least-squares problem for the ETFs most correlated with
    the current residual and keeps the one that lowers the error most, skipping any that
    would get less than `config.min_weight`. ETFs held last month get a bonus, so the
    selection does not flip between near-equivalent ETFs. It stops early once another
    ETF improves the fit by less than 0.1%; positions that end up below the minimum are
    dropped and the rest refitted.
    """
    A, b = _system(np.asarray(y, float), np.asarray(X, float), config)
    previous = np.asarray(previous, float)
    n = A.shape[1]
    cap = min(config.max_etfs or n, n)
    held = previous > 1e-4
    norms = np.linalg.norm(A, axis=0) + 1e-12
    selected: list[int] = []
    w = np.zeros(n)
    error = float(b @ b)
    while len(selected) < cap:
        scores = np.abs(A.T @ (b - A @ w)) / norms
        scores[selected] = -np.inf
        best = None
        for j in np.argsort(-scores)[:SCREEN]:
            if scores[j] == -np.inf:
                continue
            trial = _fit(A, b, previous, np.array([*selected, j]))
            if trial[j] <= 0 or trial[j] < config.min_weight:
                continue
            e = float(np.sum((b - A @ trial) ** 2))
            gain = (error - e) * (1 + STICKINESS * held[j])
            if best is None or gain > best[0]:
                best = (gain, int(j), trial, e)
        if best is None or error - best[3] < 1e-3 * error:
            break
        _, j, w, error = best
        selected.append(j)
    return _trim(A, b, previous, w, config.min_weight)


def make_estimator(config: ReplicationConfig) -> Estimator:
    """Plain least squares for long/short or levered clones, forward selection when the
    number of ETFs is capped, stable least squares otherwise."""
    if not config.long_only or config.max_gross != 1.0:
        return constrained_least_squares
    return forward_selection if config.max_etfs else stable_least_squares


DEFAULT: Estimator = stable_least_squares
