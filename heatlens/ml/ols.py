"""Tiny OLS for delta_t ~ intercept + 4 urban-form fractions. Pure Python."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence

from heatlens.domain.types import Coefficients
from heatlens.errors import ValidationFailed

RIDGE = 1e-6
LEAF_ON_MONTHS = frozenset({6, 7, 8})
SUMMER_WEIGHT = 6.0


def capture_month(captured_at) -> Optional[int]:
    if captured_at is None or captured_at == "":
        return None
    try:
        raw = float(captured_at)
    except (TypeError, ValueError):
        return None
    seconds = raw / 1000.0 if raw > 10_000_000_000 else raw
    return datetime.fromtimestamp(seconds, tz=timezone.utc).month


def is_leaf_on(row) -> bool:
    month = capture_month(row.get("captured_at"))
    return month in LEAF_ON_MONTHS


def fit_delta_t_coefficients(
    rows: Sequence[dict],
    target_canopy_frac=0.40,
    constrain_canopy=True,
) -> Coefficients:
    """Fit B1. Summer (Jun–Aug) photos get more weight; canopy is fit on leaf-on
    residuals when possible, and never shipped as a positive 'trees heat streets' coeff.
    """
    if len(rows) < 5:
        raise ValidationFailed("need at least 5 labelled rows to fit the linear model")
    weights = [SUMMER_WEIGHT if is_leaf_on(row) else 1.0 for row in rows]
    beta = _ols([_x_full(row) for row in rows], [float(row["delta_t"]) for row in rows], weights)

    leaf = [row for row in rows if is_leaf_on(row)]
    if len(leaf) >= 20:
        beta_nc = _ols(
            [_x_no_canopy(row) for row in rows],
            [float(row["delta_t"]) for row in rows],
            weights,
        )
        resid = []
        canopies = []
        leaf_w = []
        for row in leaf:
            pred = (
                beta_nc[0]
                + beta_nc[1] * float(row["asphalt_frac"])
                + beta_nc[2] * float(row["sky_frac"])
                + beta_nc[3] * float(row["building_frac"])
            )
            resid.append(float(row["delta_t"]) - pred)
            canopies.append(float(row["canopy_frac"]))
            leaf_w.append(SUMMER_WEIGHT)
        canopy = _weighted_slope(canopies, resid, leaf_w)
        intercept, asphalt, sky, building = beta_nc[0], beta_nc[1], beta_nc[2], beta_nc[3]
    else:
        intercept, canopy, asphalt, sky, building = beta[0], beta[1], beta[2], beta[3], beta[4]

    if constrain_canopy and canopy > 0:
        canopy = 0.0
        beta_nc = _ols(
            [_x_no_canopy(row) for row in rows],
            [float(row["delta_t"]) for row in rows],
            weights,
        )
        intercept, asphalt, sky, building = beta_nc[0], beta_nc[1], beta_nc[2], beta_nc[3]

    return Coefficients(
        intercept=intercept,
        canopy=canopy,
        asphalt=asphalt,
        sky=sky,
        building=building,
        target_canopy_frac=target_canopy_frac,
    )


def _x_full(row):
    return [
        1.0,
        float(row["canopy_frac"]),
        float(row["asphalt_frac"]),
        float(row["sky_frac"]),
        float(row["building_frac"]),
    ]


def _x_no_canopy(row):
    return [
        1.0,
        float(row["asphalt_frac"]),
        float(row["sky_frac"]),
        float(row["building_frac"]),
    ]


def _weighted_slope(xs, ys, weights) -> float:
    wsum = sum(weights)
    if wsum <= 0:
        return 0.0
    mx = sum(w * x for w, x in zip(weights, xs)) / wsum
    my = sum(w * y for w, y in zip(weights, ys)) / wsum
    num = sum(w * (x - mx) * (y - my) for w, x, y in zip(weights, xs, ys))
    den = sum(w * (x - mx) ** 2 for w, x in zip(weights, xs))
    if den <= 1e-12:
        return 0.0
    return num / den


def _ols(x_rows: List[List[float]], y: Sequence[float], weights: Optional[Sequence[float]] = None) -> List[float]:
    p = len(x_rows[0])
    xtx = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p
    if weights is None:
        weights = [1.0] * len(x_rows)
    for x, yi, w in zip(x_rows, y, weights):
        if len(x) != p:
            raise ValidationFailed("feature rows must all have length {0}".format(p))
        for i in range(p):
            xty[i] += w * x[i] * yi
            for j in range(p):
                xtx[i][j] += w * x[i] * x[j]
    for i in range(p):
        xtx[i][i] += RIDGE
    return _solve(xtx, xty)


def _solve(matrix: List[List[float]], rhs: List[float]) -> List[float]:
    n = len(rhs)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValidationFailed("linear system is singular; fractions may be constant")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        for j in range(col, n + 1):
            a[col][j] /= scale
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            for j in range(col, n + 1):
                a[row][j] -= factor * a[col][j]
    return [a[i][n] for i in range(n)]
