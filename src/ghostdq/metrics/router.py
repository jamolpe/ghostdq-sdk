"""Choose the best metrics backend for a file path."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from ghostdq.contract import RuleSpec, required_columns
from ghostdq.metrics.arrow import ArrowMetricsEngine
from ghostdq.metrics.engine import MetricsEngine
from ghostdq.metrics.streaming import StreamingCsvMetricsEngine
from ghostdq.reading import PandasFileReader
from ghostdq.reading.types import PathLike

MetricsBackend = Literal["auto", "pandas", "arrow", "streaming", "polars", "duckdb"]


def compute_metrics_file(
    path: PathLike,
    rules: list[RuleSpec],
    *,
    engine: MetricsBackend = "auto",
    chunksize: int = 100_000,
    columns: list[str] | None = None,
    duckdb_connection: Any | None = None,
) -> dict[str, Any]:
    """Compute metrics from a file using the requested backend.

    ``auto`` picks streaming for CSV, Arrow for Parquet, pandas otherwise.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    cols = columns if columns is not None else required_columns(rules)
    chosen = _resolve_engine(engine, suffix)

    if chosen == "streaming":
        return StreamingCsvMetricsEngine().compute(
            p,
            rules,
            columns=cols or None,
            chunksize=chunksize,
        )

    if chosen == "arrow":
        return ArrowMetricsEngine().compute_parquet(p, rules)

    if chosen == "polars":
        from ghostdq.metrics.polars_engine import PolarsMetricsEngine

        reader = PolarsMetricsEngine()
        if suffix == ".csv":
            return reader.compute_csv(p, rules, columns=cols or None)
        if suffix == ".parquet":
            return reader.compute_parquet(p, rules, columns=cols or None)
        raise ValueError(f"Polars engine does not support {suffix!r}")

    if chosen == "duckdb":
        from ghostdq.metrics.duckdb_engine import DuckDBMetricsEngine

        duckdb = __import__("duckdb")
        conn = duckdb_connection or duckdb.connect()
        return DuckDBMetricsEngine().compute_path(conn, p, rules, columns=cols or None)

    df = PandasFileReader().read(p, columns=cols or None)
    return MetricsEngine().compute(df, rules)


def _resolve_engine(engine: MetricsBackend, suffix: str) -> MetricsBackend:
    if engine != "auto":
        return engine
    if suffix == ".csv":
        return "streaming"
    if suffix == ".parquet":
        return "arrow"
    return "pandas"
