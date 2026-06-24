"""PyArrow-native metric computation (no pandas conversion)."""

from __future__ import annotations

from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

from ghostdq.contract import RuleSpec, required_columns
from ghostdq.metrics.plans import ColumnMetricsPlan, build_metric_plan
from ghostdq.reading.types import PathLike


class ArrowMetricsEngine:
    """Compute contract metrics directly from a PyArrow table."""

    def compute(self, table: pa.Table, rules: list[RuleSpec]) -> dict[str, Any]:
        work = self._narrow_table(table, rules)
        need_row_count, plans = build_metric_plan(rules)
        total = work.num_rows
        metrics: dict[str, Any] = {}

        if need_row_count:
            metrics["row_count"] = total

        for column, plan in plans.items():
            metrics.update(self._compute_for_column(work[column], column, plan, total))

        return metrics

    def compute_parquet(
        self,
        path: PathLike,
        rules: list[RuleSpec],
    ) -> dict[str, Any]:
        """Read a Parquet file into Arrow and compute metrics without pandas."""
        import pyarrow.parquet as pq

        cols = required_columns(rules)
        table = pq.read_table(path, columns=cols or None)
        return self.compute(table, rules)

    @staticmethod
    def _narrow_table(table: pa.Table, rules: list[RuleSpec]) -> pa.Table:
        needed = required_columns(rules)
        if not needed:
            return table

        missing = [col for col in needed if col not in table.column_names]
        if missing:
            raise ValueError(
                f"Column {missing[0]!r} not found in table. "
                f"Available columns: {table.column_names}"
            )

        if len(needed) < len(table.column_names):
            return table.select(needed)

        return table

    def _compute_for_column(
        self,
        array: pa.Array | pa.ChunkedArray,
        column: str,
        plan: ColumnMetricsPlan,
        total: int,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        length = len(array)

        if plan.null_rate:
            nulls = int(pc.sum(pc.is_null(array).cast(pa.int64())).as_py())
            out[f"null_rate:{column}"] = 0.0 if total == 0 else round(nulls / total, 8)

        if plan.needs_duplicate_tracking:
            dup_count = self._duplicate_count(array)
            if plan.duplicate_count:
                out[f"duplicate_count:{column}"] = dup_count
            if plan.duplicate_rate:
                out[f"duplicate_rate:{column}"] = (
                    0.0 if total == 0 else round(dup_count / total, 8)
                )

        if plan.value_min or plan.value_max:
            numeric = self._to_numeric_array(array)
            valid = pc.and_(pc.is_valid(numeric), pc.invert(pc.is_nan(numeric)))
            if not pc.any(valid).as_py():
                if plan.value_min:
                    out[f"value_min:{column}"] = float("nan")
                if plan.value_max:
                    out[f"value_max:{column}"] = float("nan")
            else:
                filtered = pc.filter(numeric, valid)
                if plan.value_min:
                    out[f"value_min:{column}"] = float(pc.min(filtered).as_py())
                if plan.value_max:
                    out[f"value_max:{column}"] = float(pc.max(filtered).as_py())

        if plan.allowed_values is not None:
            allowed_set = {str(v) for v in plan.allowed_values}
            strings = pc.cast(array, pa.string())
            allowed_values = pa.array(list(allowed_set), type=pa.string())
            allowed_mask = pc.is_in(strings, value_set=allowed_values)
            invalid = pc.invert(allowed_mask)
            nulls = pc.is_null(array)
            out[f"disallowed_count:{column}"] = int(
                pc.sum(pc.or_(invalid, nulls).cast(pa.int64())).as_py()
            )

        if length != total:
            raise RuntimeError("column length mismatch while computing metrics")

        return out

    @staticmethod
    def _duplicate_count(array: pa.Array | pa.ChunkedArray) -> int:
        non_null = pc.filter(array, pc.is_valid(array))
        if len(non_null) == 0:
            return 0

        counts_table = pc.value_counts(non_null)
        counts = counts_table.field("counts")
        mask = pc.greater(counts, 1)
        duplicate_rows = pc.filter(counts, mask)
        if len(duplicate_rows) == 0:
            return 0
        return int(pc.sum(duplicate_rows).as_py())

    @staticmethod
    def _to_numeric_array(array: pa.Array | pa.ChunkedArray) -> pa.Array | pa.ChunkedArray:
        if pa.types.is_floating(array.type) or pa.types.is_integer(array.type):
            return pc.cast(array, pa.float64())
        try:
            return pc.cast(array, pa.float64(), safe=False)
        except pa.ArrowInvalid:
            strings = pc.cast(array, pa.string())
            return pc.cast(strings, pa.float64(), safe=False)


_default_arrow_engine = ArrowMetricsEngine()


def compute_arrow_metrics(table: pa.Table, rules: list[RuleSpec]) -> dict[str, Any]:
    """Compute metrics from a PyArrow table."""
    return _default_arrow_engine.compute(table, rules)
