"""Evaluation metrics in pure Python. Used by evaluate.py and tests."""

from __future__ import annotations

import math
from typing import Sequence

from heatlens.errors import ValidationFailed


def mae(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    truth, pred = _pairs(y_true, y_pred)
    return sum(abs(a - b) for a, b in zip(truth, pred)) / float(len(truth))


def r_squared(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    truth, pred = _pairs(y_true, y_pred)
    mean = sum(truth) / float(len(truth))
    ss_tot = sum((y - mean) ** 2 for y in truth)
    ss_res = sum((y - y_hat) ** 2 for y, y_hat in zip(truth, pred))
    if ss_tot == 0:
        return 1.0 if ss_res == 0 else 0.0
    return 1.0 - (ss_res / ss_tot)


def spearman_rho(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    truth, pred = _pairs(y_true, y_pred)
    return _pearson(_ranks(truth), _ranks(pred))


def top_decile_precision(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    truth, pred = _pairs(y_true, y_pred)
    n = len(truth)
    k = max(int(math.ceil(n * 0.10)), 1)
    true_hot = set(sorted(range(n), key=lambda i: truth[i], reverse=True)[:k])
    pred_hot = set(sorted(range(n), key=lambda i: pred[i], reverse=True)[:k])
    return len(true_hot & pred_hot) / float(k)


def _pairs(y_true, y_pred):
    truth = [float(v) for v in y_true]
    pred = [float(v) for v in y_pred]
    if len(truth) != len(pred) or not truth:
        raise ValidationFailed("y_true and y_pred must be non-empty and the same length")
    return truth, pred


def _ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(xs, ys):
    n = float(len(xs))
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)
