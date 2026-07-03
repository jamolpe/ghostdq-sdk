"""Incremental metric state for chunked CSV processing.

Provides :class:`ColumnAccumulator` and :class:`StreamingState`, used exclusively
by :class:`~ghostdq.metrics.StreamingCsvMetricsEngine` to compute the same metric
keys as :class:`~ghostdq.metrics.MetricsEngine` without loading the full file.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ghostdq.metrics.checks import is_out_of_range, regex_matches
from ghostdq.metrics.plans import ColumnMetricsPlan


@dataclass
class ColumnAccumulator:
    """Incremental per-column counters for chunked CSV scans.

    One instance per column in a :class:`StreamingState`. Each incoming chunk
    calls :meth:`update`; :meth:`finalize` converts running totals into the same
    metric keys produced by :class:`~ghostdq.metrics.MetricsEngine`.

    Attributes:
        null_count: Rows counted as null (including ``""``).
        disallowed_count: Rows not in the allowed-values set.
        out_of_range_count: Rows failing row-level min/max checks.
        regex_match_count: Rows matching the configured regex pattern.
        value_min: Running minimum of numeric values seen so far.
        value_max: Running maximum of numeric values seen so far.
        saw_numeric: Whether any parseable numeric value was observed.
        value_counts: Per-value frequencies for duplicate detection (optional).
    """

    null_count: int = 0
    disallowed_count: int = 0
    out_of_range_count: int = 0
    regex_match_count: int = 0
    value_min: float | None = None
    value_max: float | None = None
    saw_numeric: bool = False
    value_counts: Counter[Any] | None = None
    _regex: re.Pattern[str] | None = field(default=None, repr=False)

    def update(self, values: list[Any], plan: ColumnMetricsPlan) -> None:
        """Incorporate one chunk of cell values according to *plan*."""
        if plan.regex_match_rate and plan.regex_pattern is not None and self._regex is None:
            self._regex = re.compile(plan.regex_pattern)

        for value in values:
            if plan.null_rate and _is_null(value):
                self.null_count += 1

            if plan.allowed_values is not None and not _is_allowed(value, plan.allowed_values):
                self.disallowed_count += 1

            if plan.out_of_range_rate:
                if is_out_of_range(
                    value,
                    min_val=plan.out_of_range_min,
                    max_val=plan.out_of_range_max,
                ):
                    self.out_of_range_count += 1

            if plan.regex_match_rate and self._regex is not None:
                if regex_matches(value, self._regex):
                    self.regex_match_count += 1

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
        """Emit metric key/value pairs for this column (e.g. ``null_rate:country``)."""
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

        if plan.out_of_range_rate:
            out[f"out_of_range_rate:{column}"] = (
                0.0 if total == 0 else round(self.out_of_range_count / total, 8)
            )

        if plan.regex_match_rate:
            out[f"regex_match_rate:{column}"] = (
                0.0 if total == 0 else round(self.regex_match_count / total, 8)
            )

        return out


@dataclass
class StreamingState:
    """Mutable scan state for :class:`~ghostdq.metrics.StreamingCsvMetricsEngine`.

    Reads CSV rows in fixed-size chunks, delegates per-column work to
    :class:`ColumnAccumulator`, and produces the final metrics dict when the
    file has been fully scanned.

    Attributes:
        row_count: Total rows observed across all chunks.
        columns: Per-column accumulators keyed by column name.
    """

    row_count: int = 0
    columns: dict[str, ColumnAccumulator] = field(default_factory=dict)

    def observe_chunk(self, chunk_rows: list[dict[str, Any]], plans: dict[str, ColumnMetricsPlan]) -> None:
        """Update accumulators with one batch of row dicts."""
        self.row_count += len(chunk_rows)
        for column, plan in plans.items():
            acc = self.columns.setdefault(column, ColumnAccumulator())
            acc.update([row.get(column) for row in chunk_rows], plan)

    def finalize(
        self,
        need_row_count: bool,
        plans: dict[str, ColumnMetricsPlan],
    ) -> dict[str, Any]:
        """Build the metrics dict after the last chunk has been processed."""
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
