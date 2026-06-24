"""DuckDB-backed metric computation (optional dependency)."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ghostdq.contract import RuleSpec, required_columns
from ghostdq.metrics.plans import ColumnMetricsPlan, build_metric_plan
from ghostdq.reading.types import PathLike


def _import_duckdb():
    try:
        return importlib.import_module("duckdb")
    except ImportError as exc:
        raise ImportError(
            "DuckDB support requires the optional dependency. "
            "Install with: pip install 'ghostdq[duckdb]'"
        ) from exc


class DuckDBMetricsEngine:
    """Compute contract metrics with DuckDB SQL over files or tables."""

    def compute(
        self,
        connection: Any,
        source: str,
        rules: list[RuleSpec],
    ) -> dict[str, Any]:
        """Compute metrics from a DuckDB table expression or view name."""
        need_row_count, plans = build_metric_plan(rules)
        metrics: dict[str, Any] = {}

        if need_row_count:
            metrics["row_count"] = int(
                connection.execute(f"SELECT COUNT(*)::BIGINT FROM {source}").fetchone()[0]
            )

        total = metrics.get("row_count")
        if total is None and plans:
            total = int(connection.execute(f"SELECT COUNT(*)::BIGINT FROM {source}").fetchone()[0])

        for column, plan in plans.items():
            metrics.update(self._compute_column(connection, source, column, plan, total or 0))

        return metrics

    def compute_path(
        self,
        connection: Any,
        path: PathLike,
        rules: list[RuleSpec],
        *,
        columns: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        source = self._source_for_path(path, columns=columns or required_columns(rules))
        return self.compute(connection, source, rules)

    @staticmethod
    def _source_for_path(path: PathLike, columns: Sequence[str] | None) -> str:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")

        quoted = str(p).replace("'", "''")
        suffix = p.suffix.lower()

        if suffix == ".csv":
            base = f"read_csv('{quoted}', header = true)"
        elif suffix == ".parquet":
            base = f"read_parquet('{quoted}')"
        else:
            raise ValueError(
                f"DuckDB engine supports .csv and .parquet files, not {suffix!r}"
            )

        if not columns:
            return base

        selected = ", ".join(f'"{col.replace(chr(34), chr(34)*2)}"' for col in columns)
        return f"(SELECT {selected} FROM {base})"

    @staticmethod
    def _compute_column(
        connection: Any,
        source: str,
        column: str,
        plan: ColumnMetricsPlan,
        total: int,
    ) -> dict[str, Any]:
        col = column.replace('"', '""')
        out: dict[str, Any] = {}

        if plan.null_rate:
            value = connection.execute(
                f"""
                SELECT COALESCE(
                    SUM(CASE WHEN "{col}" IS NULL THEN 1 ELSE 0 END), 0
                )::DOUBLE / NULLIF(COUNT(*), 0)
                FROM {source}
                """
            ).fetchone()[0]
            out[f"null_rate:{column}"] = 0.0 if total == 0 or value is None else round(float(value), 8)

        if plan.needs_duplicate_tracking:
            dup_count = int(
                connection.execute(
                    f"""
                    SELECT COALESCE(SUM(group_count), 0)::BIGINT
                    FROM (
                        SELECT COUNT(*) AS group_count
                        FROM {source}
                        GROUP BY "{col}"
                        HAVING COUNT(*) > 1
                    ) dupes
                    """
                ).fetchone()[0]
            )
            if plan.duplicate_count:
                out[f"duplicate_count:{column}"] = dup_count
            if plan.duplicate_rate:
                out[f"duplicate_rate:{column}"] = (
                    0.0 if total == 0 else round(dup_count / total, 8)
                )

        if plan.value_min or plan.value_max:
            row = connection.execute(
                f"""
                SELECT
                    MIN(TRY_CAST("{col}" AS DOUBLE)),
                    MAX(TRY_CAST("{col}" AS DOUBLE))
                FROM {source}
                """
            ).fetchone()
            if plan.value_min:
                out[f"value_min:{column}"] = float("nan") if row[0] is None else float(row[0])
            if plan.value_max:
                out[f"value_max:{column}"] = float("nan") if row[1] is None else float(row[1])

        if plan.allowed_values is not None:
            allowed = ", ".join(f"'{str(v).replace(chr(39), chr(39)*2)}'" for v in plan.allowed_values)
            bad = int(
                connection.execute(
                    f"""
                    SELECT COALESCE(SUM(
                        CASE
                            WHEN "{col}" IS NULL THEN 1
                            WHEN CAST("{col}" AS VARCHAR) NOT IN ({allowed}) THEN 1
                            ELSE 0
                        END
                    ), 0)::BIGINT
                    FROM {source}
                    """
                ).fetchone()[0]
            )
            out[f"disallowed_count:{column}"] = bad

        return out
