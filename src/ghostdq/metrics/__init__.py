"""Data-quality metric computation."""

from ghostdq.metrics.arrow import ArrowMetricsEngine, compute_arrow_metrics
from ghostdq.metrics.duckdb_engine import DuckDBMetricsEngine
from ghostdq.metrics.engine import MetricsEngine, compute_metrics
from ghostdq.metrics.polars_engine import PolarsMetricsEngine
from ghostdq.metrics.router import MetricsBackend, compute_metrics_file
from ghostdq.metrics.streaming import StreamingCsvMetricsEngine, compute_csv_streaming

__all__ = [
    "ArrowMetricsEngine",
    "DuckDBMetricsEngine",
    "MetricsBackend",
    "MetricsEngine",
    "PolarsMetricsEngine",
    "StreamingCsvMetricsEngine",
    "compute_arrow_metrics",
    "compute_csv_streaming",
    "compute_metrics",
    "compute_metrics_file",
]
