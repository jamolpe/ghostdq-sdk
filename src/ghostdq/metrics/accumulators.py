"""Incremental metric state for chunked CSV processing."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ghostdq.metrics.plans import ColumnMetricsPlan


@dataclass
class ColumnAccumulator:
    null_count: int = 0
    disallowed_count: int = 0
    value_min: float | None = None
    value_max: float | None = None
    saw_numeric: bool = False
    value_counts: Counter[Any] | None = None

    def update(self, values: list[Any], plan: ColumnMetricsPlan) -> None:
        for value in values:
            if plan.null_rate and _is_null(value):
                self.null_count += 1

            if plan.allowed_values is not None and not _is_allowed(value, plan.allowed_values):
                self.disallowed_count += 1

            if plan.value_min or plan.value_max:
                numeric = _to_float(value)
                if numeric is not None and not math.isnan(numeric):
                    self.saw_numeric = True
                    self.value_min = numeric if self.value_min is None else min(self.value_min, numeric)
                    self.value_max = numeric if self.value_max is None else max(self.value_max, numeric)

            if plan.needs_duplicate_tracking:
                if self.value_counts is None:
                    self.value_counts = Counter()
                if not _is_null(value):
                    self.value_counts[value] += 1

    def finalize(self, column: str, plan: ColumnMetricsPlan, total: int) -> dict[str, Any]:
        out: dict[str, Any] = {}

        if plan.null_rate:
            out[f"null_rate:{column}"] = 0.0 if total == 0 else round(self.null_count / total, 8)

        if plan.needs_duplicate_tracking:
            dup_count = 0
            if self.value_counts is not None:
                dup_count = sum(count for count in self.value_counts.values() if count > 1)
            if plan.duplicate_count:
                out[f"duplicate_count:{column}"] = dup_count
            if plan.duplicate_rate:
                out[f"duplicate_rate:{column}"] = 0.0 if total == 0 else round(dup_count / total, 8)

        if plan.value_min:
            out[f"value_min:{column}"] = float("nan") if not self.saw_numeric else float(self.value_min)
        if plan.value_max:
            out[f"value_max:{column}"] = float("nan") if not self.saw_numeric else float(self.value_max)

        if plan.allowed_values is not None:
            out[f"disallowed_count:{column}"] = self.disallowed_count

        return out


@dataclass
class StreamingState:
    row_count: int = 0
    columns: dict[str, ColumnAccumulator] = field(default_factory=dict)

    def observe_chunk(self, chunk_rows: list[dict[str, Any]], plans: dict[str, ColumnMetricsPlan]) -> None:
        self.row_count += len(chunk_rows)
        for column, plan in plans.items():
            acc = self.columns.setdefault(column, ColumnAccumulator())
            acc.update([row.get(column) for row in chunk_rows], plan)

    def finalize(
        self,
        need_row_count: bool,
        plans: dict[str, ColumnMetricsPlan],
    ) -> dict[str, Any]:
        metrics: dict[str, Any] = {}
        if need_row_count:
            metrics["row_count"] = self.row_count

        for column, plan in plans.items():
            acc = self.columns.setdefault(column, ColumnAccumulator())
            metrics.update(acc.finalize(column, plan, self.row_count))

        return metrics


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value == "":
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def _is_allowed(value: Any, allowed: list[Any]) -> bool:
    if _is_null(value):
        return False
    allowed_set = {str(v) for v in allowed}
    return str(value) in allowed_set


def _to_float(value: Any) -> float | None:
    if _is_null(value):
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return float("nan")
