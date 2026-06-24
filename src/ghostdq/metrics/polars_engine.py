"""Polars-backed metric computation (optional dependency)."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import Any

from ghostdq.contract import RuleSpec, required_columns
from ghostdq.metrics.plans import build_metric_plan
from ghostdq.reading.types import PathLike


def _import_polars():
    try:
        return importlib.import_module("polars")
    except ImportError as exc:
        raise ImportError(
            "Polars support requires the optional dependency. "
            "Install with: pip install 'ghostdq[polars]'"
        ) from exc


class PolarsMetricsEngine:
    """Compute contract metrics from a Polars LazyFrame or DataFrame."""

    def compute(self, frame: Any, rules: list[RuleSpec]) -> dict[str, Any]:
        pl = _import_polars()
        lazy = frame.lazy() if isinstance(frame, pl.DataFrame) else frame
        needed = required_columns(rules)
        if needed:
            lazy = lazy.select(needed)

        schema = lazy.collect_schema()
        if needed:
            missing = [col for col in needed if col not in schema.names()]
            if missing:
                raise ValueError(
                    f"Column {missing[0]!r} not found in frame. "
                    f"Available columns: {schema.names()}"
                )

        need_row_count, plans = build_metric_plan(rules)
        metrics: dict[str, Any] = {}
        total = int(lazy.select(pl.len()).collect().item())

        if need_row_count:
            metrics["row_count"] = total

        for column, plan in plans.items():
            exprs: list[Any] = []

            if plan.null_rate:
                exprs.append(
                    (pl.col(column).null_count() / pl.len()).alias(f"null_rate:{column}")
                )

            if plan.duplicate_count:
                exprs.append(
                    pl.col(column)
                    .filter(pl.col(column).is_duplicated())
                    .len()
                    .alias(f"duplicate_count:{column}")
                )

            if plan.duplicate_rate:
                exprs.append(
                    (
                        pl.col(column).filter(pl.col(column).is_duplicated()).len() / pl.len()
                    ).alias(f"duplicate_rate:{column}")
                )

            if plan.value_min:
                exprs.append(
                    pl.col(column).cast(pl.Float64, strict=False).min().alias(f"value_min:{column}")
                )

            if plan.value_max:
                exprs.append(
                    pl.col(column).cast(pl.Float64, strict=False).max().alias(f"value_max:{column}")
                )

            if plan.allowed_values is not None:
                allowed = [str(v) for v in plan.allowed_values]
                exprs.append(
                    (
                        pl.col(column).is_null()
                        | pl.col(column).cast(pl.Utf8).is_in(allowed).not_()
                    )
                    .sum()
                    .alias(f"disallowed_count:{column}")
                )

            if not exprs:
                continue

            row = lazy.select(exprs).collect().to_dicts()[0]
            for key, value in row.items():
                if key.startswith("null_rate:") or key.startswith("duplicate_rate:"):
                    metrics[key] = 0.0 if total == 0 else round(float(value or 0.0), 8)
                elif key.startswith("value_min:") or key.startswith("value_max:"):
                    metrics[key] = float("nan") if value is None else float(value)
                else:
                    metrics[key] = int(value or 0)

        return metrics

    def compute_csv(
        self,
        path: PathLike,
        rules: list[RuleSpec],
        *,
        columns: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        pl = _import_polars()
        needed = list(columns) if columns is not None else required_columns(rules)
        source = pl.scan_csv(path)
        if needed:
            source = source.select(needed)
        return self.compute(source, rules)

    def compute_parquet(
        self,
        path: PathLike,
        rules: list[RuleSpec],
        *,
        columns: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        pl = _import_polars()
        needed = list(columns) if columns is not None else required_columns(rules)
        source = pl.scan_parquet(path)
        if needed:
            source = source.select(needed)
        return self.compute(source, rules)
