"""Metric computation engines — one subpackage per backend."""

from ghostdq.metrics.engines.arrow.engine import ArrowMetricsEngine, compute_arrow_metrics
from ghostdq.metrics.engines.pandas.engine import MetricsEngine, compute_metrics
from ghostdq.metrics.engines.streaming.engine import (
    StreamingCsvMetricsEngine,
    compute_csv_streaming,
)

__all__ = [
    "ArrowMetricsEngine",
    "MetricsEngine",
    "StreamingCsvMetricsEngine",
    "compute_arrow_metrics",
    "compute_csv_streaming",
    "compute_metrics",
]
