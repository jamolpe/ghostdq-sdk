"""Compute data-quality metrics from a pandas DataFrame."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ghostdq.contract import RuleSpec, required_columns
from ghostdq.metrics.plans import ColumnMetricsPlan, build_metric_plan


class MetricsEngine:
    """Compute contract metrics from a pandas DataFrame."""

    def compute(self, df: pd.DataFrame, rules: list[RuleSpec]) -> dict[str, Any]:
        """Compute all metric keys required by the given rules."""
        work = self._narrow_to_required_columns(df, rules)
        need_row_count, plans = build_metric_plan(rules)
        total = len(work)
        metrics: dict[str, Any] = {}

        if need_row_count:
            metrics["row_count"] = total

        for column, plan in plans.items():
            metrics.update(self._compute_for_column(work[column], column, plan, total))

        return metrics

    @staticmethod
    def _narrow_to_required_columns(df: pd.DataFrame, rules: list[RuleSpec]) -> pd.DataFrame:
        needed = required_columns(rules)
        if not needed:
            return df

        missing = [col for col in needed if col not in df.columns]
        if missing:
            raise ValueError(
                f"Column {missing[0]!r} not found in DataFrame. "
                f"Available columns: {list(df.columns)}"
            )

        if len(needed) < len(df.columns):
            return df[needed]

        return df

    @staticmethod
    def _compute_for_column(
        series: pd.Series,
        column: str,
        plan: ColumnMetricsPlan,
        total: int,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}

        if plan.null_rate:
            if total == 0:
                out[f"null_rate:{column}"] = 0.0
            else:
                out[f"null_rate:{column}"] = round(int(series.isna().sum()) / total, 8)

        if plan.duplicate_count or plan.duplicate_rate:
            dup_count = int(series.duplicated(keep=False).sum())
            if plan.duplicate_count:
                out[f"duplicate_count:{column}"] = dup_count
            if plan.duplicate_rate:
                out[f"duplicate_rate:{column}"] = (
                    0.0 if total == 0 else round(dup_count / total, 8)
                )

        if plan.value_min or plan.value_max:
            numeric = pd.to_numeric(series, errors="coerce")
            all_nan = bool(numeric.isna().all())
            if plan.value_min:
                out[f"value_min:{column}"] = float("nan") if all_nan else float(numeric.min())
            if plan.value_max:
                out[f"value_max:{column}"] = float("nan") if all_nan else float(numeric.max())

        if plan.allowed_values is not None:
            allowed_set = {str(v) for v in plan.allowed_values}
            out[f"disallowed_count:{column}"] = int(
                (~series.astype(str).isin(allowed_set)).sum()
            )

        return out


_default_engine = MetricsEngine()


def compute_metrics(df: pd.DataFrame, rules: list[RuleSpec]) -> dict[str, Any]:
    """Compute metrics using the default :class:`MetricsEngine`."""
    return _default_engine.compute(df, rules)
