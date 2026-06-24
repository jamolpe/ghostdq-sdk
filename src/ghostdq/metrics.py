"""Compute data-quality metrics from a pandas DataFrame.

Each function produces the metric keys that the server-side evaluator expects
(defined in ghostdq_core.rules). The names must stay in sync:

  row_count         → int
  null_rate:{col}   → float in [0.0, 1.0]
  duplicate_count:{col} → int
  duplicate_rate:{col}  → float in [0.0, 1.0]
  value_min:{col}   → number
  value_max:{col}   → number
  disallowed_count:{col} → int

This module is intentionally side-effect-free: given a DataFrame and a list
of RuleSpecs, it returns a plain dict. No network, no DB, no files.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ghostdq.contract import RuleSpec


def compute_metrics(df: pd.DataFrame, rules: list[RuleSpec]) -> dict[str, Any]:
    """Compute all metric keys required by the given rules.

    Returns a flat dict of metric_name → scalar value ready to POST to the
    Ingest API.
    """
    metrics: dict[str, Any] = {}
    for rule in rules:
        for key in rule.metric_keys():
            if key in metrics:
                continue  # already computed by a previous rule
            metrics[key] = _compute_one(df, key, rule)
    return metrics


# ---------------------------------------------------------------------------
# Internal dispatchers
# ---------------------------------------------------------------------------

def _compute_one(df: pd.DataFrame, metric_key: str, rule: RuleSpec) -> Any:
    col = rule.params.get("column")

    if metric_key == "row_count":
        return _row_count(df)

    if metric_key.startswith("null_rate:") and col:
        return _null_rate(df, col)

    if metric_key.startswith("duplicate_count:") and col:
        return _duplicate_count(df, col)

    if metric_key.startswith("duplicate_rate:") and col:
        return _duplicate_rate(df, col)

    if metric_key.startswith("value_min:") and col:
        return _value_min(df, col)

    if metric_key.startswith("value_max:") and col:
        return _value_max(df, col)

    if metric_key.startswith("disallowed_count:") and col:
        allowed = rule.params.get("values", [])
        return _disallowed_count(df, col, allowed)

    raise ValueError(f"Don't know how to compute metric {metric_key!r}")


# ---------------------------------------------------------------------------
# Individual metric computers
# ---------------------------------------------------------------------------

def _row_count(df: pd.DataFrame) -> int:
    return len(df)


def _null_rate(df: pd.DataFrame, column: str) -> float:
    _assert_column(df, column)
    total = len(df)
    if total == 0:
        return 0.0
    null_count = int(df[column].isna().sum())
    return round(null_count / total, 8)


def _duplicate_count(df: pd.DataFrame, column: str) -> int:
    _assert_column(df, column)
    # Count rows whose value appears more than once (all duplicates, not just extra ones).
    return int(df[column].duplicated(keep=False).sum())


def _duplicate_rate(df: pd.DataFrame, column: str) -> float:
    _assert_column(df, column)
    total = len(df)
    if total == 0:
        return 0.0
    return round(_duplicate_count(df, column) / total, 8)


def _value_min(df: pd.DataFrame, column: str) -> float:
    _assert_column(df, column)
    col = pd.to_numeric(df[column], errors="coerce")
    if col.isna().all():
        return float("nan")
    return float(col.min())


def _value_max(df: pd.DataFrame, column: str) -> float:
    _assert_column(df, column)
    col = pd.to_numeric(df[column], errors="coerce")
    if col.isna().all():
        return float("nan")
    return float(col.max())


def _disallowed_count(df: pd.DataFrame, column: str, allowed: list[Any]) -> int:
    _assert_column(df, column)
    allowed_set = set(str(v) for v in allowed)
    # Cast column to str for comparison — contracts store values as strings.
    return int((~df[column].astype(str).isin(allowed_set)).sum())


def _assert_column(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        raise ValueError(
            f"Column {column!r} not found in file. "
            f"Available columns: {list(df.columns)}"
        )
